/**
 * Puerta por Web Serial API (Chrome / Edge).
 * El Arduino debe estar en la misma PC que el navegador.
 */
window.GymPuertaSerial = (function () {
    const BAUD = 9600;
    const OPEN_DELAY_MS = 2000;

    function esperar(ms) {
        return new Promise(function (r) { setTimeout(r, ms); });
    }

    function soportado() {
        return typeof navigator !== 'undefined' && 'serial' in navigator;
    }

    function PuertaSerial(pulsoMs) {
        this.pulsoMs = pulsoMs || 3000;
        this.port = null;
        this.abierto = false;
    }

    PuertaSerial.prototype._leerLinea = async function (timeoutMs) {
        if (!this.port || !this.port.readable) return '';
        const reader = this.port.readable.getReader();
        const decoder = new TextDecoder();
        let buf = '';
        const deadline = Date.now() + timeoutMs;
        try {
            while (Date.now() < deadline) {
                const { value, done } = await Promise.race([
                    reader.read(),
                    esperar(80).then(function () { return { value: null, done: false }; }),
                ]);
                if (value) {
                    buf += decoder.decode(value);
                    if (buf.indexOf('\n') >= 0) return buf.split('\n')[0].trim();
                }
                if (done) break;
            }
        } finally {
            reader.releaseLock();
        }
        return '';
    };

    PuertaSerial.prototype._abrirPuerto = async function () {
        if (!this.port) return false;
        if (!this.abierto) {
            await this.port.open({ baudRate: BAUD });
            this.abierto = true;
            await esperar(OPEN_DELAY_MS);
        }
        return true;
    };

    PuertaSerial.prototype.reconectarAutomatico = async function () {
        if (!soportado()) return false;
        try {
            const ports = await navigator.serial.getPorts();
            if (!ports.length) return false;
            this.port = ports[0];
            await this._abrirPuerto();
            return true;
        } catch (e) {
            console.warn('Puerta serial:', e);
            this.abierto = false;
            return false;
        }
    };

    PuertaSerial.prototype.conectar = async function () {
        if (!soportado()) {
            throw new Error('Usá Google Chrome o Microsoft Edge en la PC donde está el Arduino.');
        }
        this.port = await navigator.serial.requestPort();
        this.abierto = false;
        await this._abrirPuerto();
        return true;
    };

    PuertaSerial.prototype.enviarComando = async function (cmd, esperado, timeoutMs) {
        if (!this.port) return false;
        await this._abrirPuerto();
        const writer = this.port.writable.getWriter();
        await writer.write(new TextEncoder().encode(cmd + '\n'));
        writer.releaseLock();
        if (!esperado) return true;
        const resp = await this._leerLinea(timeoutMs || 3000);
        return resp === esperado;
    };

    PuertaSerial.prototype.abrirPuerta = async function () {
        const ms = Math.max(500, Math.min(30000, this.pulsoMs));
        const ok = await this.enviarComando('UNLOCK ' + ms, 'OK', ms + 3000);
        return ok;
    };

    PuertaSerial.prototype.probar = async function () {
        return this.enviarComando('PING', 'PONG', 3000);
    };

    return {
        soportado: soportado,
        crear: function (pulsoMs) { return new PuertaSerial(pulsoMs); },
    };
})();
