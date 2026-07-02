from django.urls import path
from gimnasio import views
from gimnasio import views_rutinas, views_socio, views_turnos, views_puerta

urlpatterns = [
    path('', views.index, name="index"),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('sistema-pausado/', views.sistema_pausado, name='sistema_pausado'),
    path('sistema-pausa/toggle/', views.toggle_sistema_pausa, name='toggle_sistema_pausa'),
    path('sistema-pausa/pagado/', views.marcar_sistema_pagado, name='marcar_sistema_pagado'),
    path('set-gimnasio/<int:gimnasio_id>/', views.set_gimnasio_actual, name='set_gimnasio_actual'),

    ##SOCIOS
    path('socios/', views.lista_socios, name='lista_socios'),
    path('socios/crear/', views.crear_socio, name='crear_socio'),
    path('socios/editar/<int:pk>/', views.editar_socio, name='editar_socio'),
    path('socios/eliminar/<int:pk>/', views.eliminar_socio, name='eliminar_socio'),
    path('socios/detalle/<int:pk>/', views.detalle_socio, name='detalle_socio'),
    path('socios/<int:pk>/mensaje/', views.enviar_mensaje_socio, name='enviar_mensaje_socio'),

    ##TIPOS DE USUARIOS
    path('tipos-usuario/', views.tipo_usuario_list, name='tipo_usuario_list'),
    path('tipos-usuario/crear/', views.tipo_usuario_create, name='tipo_usuario_create'),
    path('tipos-usuario/editar/<int:pk>/', views.tipo_usuario_update, name='tipo_usuario_update'),
    path('tipos-usuario/eliminar/<int:pk>/', views.tipo_usuario_delete, name='tipo_usuario_delete'),

    ##USUARIOS
    path('usuarios/crear/', views.usuario_create, name='usuario_create'),
    path('usuarios/lista/', views.usuario_list, name='usuario_list'),
    path('usuarios/editar/<int:pk>/', views.usuario_update, name='usuario_update'),
    path('usuarios/eliminar/<int:pk>/', views.usuario_delete, name='usuario_delete'),
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('reset-password/<int:pk>/', views.password_reset_confirm, name='password_reset_confirm'),

    ## gym
    path('gimnasios/', views.gimnasio_lista, name='gimnasio_lista'),
    path('gimnasios/crear/', views.gimnasio_crear, name='gimnasio_crear'),
    path('gimnasios/editar/<int:pk>/', views.gimnasio_editar, name='gimnasio_editar'),
    path('gimnasios/eliminar/<int:pk>/', views.gimnasio_eliminar, name='gimnasio_eliminar'),
    path('gimnasios/<int:pk>/', views.gimnasio_detalle, name='gimnasio_detalle'),

    ##tipo de mensualidad
    path('tipos/', views.lista_tipos_mensualidad, name='lista_tipos_mensualidad'),
    path('tipos/nueva/', views.crear_plan_mensualidad, name='crear_plan_mensualidad'),
    path('tipos/plan/<int:categoria_id>/', views.detalle_plan_mensualidad, name='detalle_plan_mensualidad'),
    path('tipos/plan/<int:categoria_id>/opcion/nueva/', views.crear_opcion_mensualidad, name='crear_opcion_mensualidad'),
    path('tipos/editar/<int:pk>/', views.editar_tipo_mensualidad, name='editar_tipo_mensualidad'),
    path('tipos/eliminar/<int:pk>/', views.eliminar_tipo_mensualidad, name='eliminar_tipo_mensualidad'),

    ##cuotas
    path('asignar_mensualidad/', views.asignar_mensualidad, name='asignar_mensualidad'),
    path('cobrar-mensualidad/<int:socio_id>/', views.cobrar_mensualidad, name='cobrar_mensualidad'),
    path('lista_cuotas/', views.lista_cuotas, name='lista_cuotas'),
    path('renovar_mensualidad/', views.renovar_mensualidad, name='renovar_mensualidad'),
    path('renovar_mensualidad_manual/', views.renovar_mensualidad_manual, name='renovar_mensualidad_manual'),

    ## profesores
    path('profesores/', views.profesor_list, name='profesor_list'),
    path('profesores/crear/', views.profesor_crear, name='profesor_crear'),
    path('profesores/<int:pk>/', views.profesor_detalle, name='profesor_detalle'),
    path('profesores/<int:pk>/editar/', views.profesor_editar, name='profesor_editar'),
    path('profesores/<int:profesor_id>/adelanto/', views.adelanto_crear, name='adelanto_crear'),
    path('profesores/pago/<int:pk>/detalle/', views.pago_profesor_detalle, name='pago_profesor_detalle'),

    ## productos y ventas
    path('productos/', views.producto_list, name='producto_list'),
    path('productos/crear/', views.producto_crear, name='producto_crear'),
    path('productos/editar/<int:pk>/', views.producto_editar, name='producto_editar'),
    path('producto_precio/<int:pk>/', views.producto_precio, name='producto_precio'),
    path('productos/eliminar/<int:pk>/', views.producto_eliminar, name='producto_eliminar'),
    path('ventas/', views.venta_list, name='venta_list'),
    path('ventas/crear/', views.venta_crear, name='venta_crear'),

    ## GASTOS
    path('gastos/', views.gastos_list, name='gastos_list'),
    path('gastos/crear/', views.gastos_crear, name='gastos_crear'),
    path('gastos/eliminar/<int:pk>/', views.gastos_eliminar, name='gastos_eliminar'),
    ## EXTRAS (legacy)
    path('extras/', views.extras_list, name='extras_list'),
    path('extras/create/', views.extras_create, name='extras_create'),
    path('extras/<int:pk>/update/', views.extras_update, name='extras_update'),
    path('extras/<int:pk>/delete/', views.extras_delete, name='extras_delete'),

    ## historiales
    path('historiales/', views.historiales_index, name='historiales_index'),
    path('historiales/reporte/', views.historiales_reporte, name='historiales_reporte'),

    ##caja diaria
    path('balance/', views.balance_diario, name='balance_diario'),
    path('balance/<int:gimnasio_id>/', views.mostrar_balance, name='mostrar_balance'),
    path('historial-cajas/', views.historial_cajas, name='historial_cajas'),
    path('caja/detalle/<int:caja_id>/', views.detalle_caja, name='detalle_caja'),
    path('caja/abrir/<int:gimnasio_id>/', views.caja_abrir, name='caja_abrir'),
    path('caja/cerrar/<int:gimnasio_id>/', views.caja_cerrar, name='caja_cerrar'),
    path('historial/', views.historial_balances, name='historial_balances'),
    path('detalle_balance/<int:balance_id>/', views.detalle_balance, name='detalle_balance'),

    ##lista de ingresos
    path('listado-ingresos/', views.listado_ingresos_diarios, name='listado_ingresos'),
    path('historial_ingresos/', views.historial_ingresos, name='historial_ingresos'),
    path('detalle_ingresos/<str:fecha>/', views.detalle_ingresos_dia, name='detalle_ingresos_dia'),
    path('api/registrar-ingreso/', views.registrar_ingreso, name='registrar_ingreso'),

    ##api socios
    path('api/socios/', views.api_socios, name='api_socios'),
    path('api/socios/<int:socio_id>/', views.api_socios, name='api_socios_detail'),

    ## API categorías y mensualidades
    path('api/categorias/', views.api_categorias, name='api_categorias'),
    path('api/mensualidades/', views.api_mensualidades_por_categoria, name='api_mensualidades_por_categoria'),
    path('api/ingreso-dni/', views.api_ingreso_por_dni, name='api_ingreso_por_dni'),

    ## Pantalla de ingreso
    path('pantalla-ingreso/', views.pantalla_ingreso, name='pantalla_ingreso'),
    path('pantalla-ingreso/kiosk/', views.pantalla_ingreso_kiosk, name='pantalla_ingreso_kiosk'),

    ## Puerta Arduino
    path('configuracion-puerta/', views_puerta.configuracion_puerta, name='configuracion_puerta'),
    path('configuracion-puerta/descargar-json/', views_puerta.descargar_agente_puerta_json, name='descargar_agente_puerta_json'),
    path('api/puerta/agente-config/', views_puerta.api_puerta_agente_config, name='api_puerta_agente_config'),

    ## Portal socios
    path('socio/login/', views_socio.socio_login, name='socio_login'),
    path('socio/portal/', views_socio.socio_portal, name='socio_portal'),
    path('socio/portal/reservar/', views_socio.socio_reservar_turno, name='socio_reservar_turno'),
    path('socio/portal/cancelar/<int:pk>/', views_socio.socio_cancelar_turno, name='socio_cancelar_turno'),
    path('socio/logout/', views_socio.socio_logout, name='socio_logout'),
    path('socio/qr/', views_socio.socio_qr_info, name='socio_qr_info'),
    path('socio/qr/imprimir/', views_socio.socio_qr_imprimir, name='socio_qr_imprimir'),

    ## Rutinas
    path('rutinas/', views_rutinas.rutinas_lista, name='rutinas_lista'),
    path('rutinas/nueva/', views_rutinas.rutina_crear, name='rutina_crear'),
    path('rutinas/<int:pk>/editar/', views_rutinas.rutina_editar, name='rutina_editar'),
    path('rutinas/<int:pk>/eliminar/', views_rutinas.rutina_eliminar, name='rutina_eliminar'),
    path('rutinas/<int:pk>/enviar/', views_rutinas.rutina_enviar, name='rutina_enviar'),
    path('rutinas/envios/', views_rutinas.envios_lista, name='envios_lista'),
    path('rutinas/envios/nueva/', views_rutinas.envio_crear, name='envio_crear'),
    path('rutinas/envios/<int:pk>/editar/', views_rutinas.envio_editar, name='envio_editar'),
    path('rutinas/envios/<int:pk>/enviar/', views_rutinas.envio_enviar, name='envio_enviar'),
    path('api/ejercicios-catalogo/', views_rutinas.api_ejercicios_catalogo, name='api_ejercicios_catalogo'),

    ## Turnos
    path('turnos/', views_turnos.turnos_index, name='turnos_index'),
    path('turnos/categoria/<int:categoria_id>/', views_turnos.turnos_horarios, name='turnos_horarios'),
    path('turnos/categoria/<int:categoria_id>/reservas/', views_turnos.turnos_reservas, name='turnos_reservas'),
    path('turnos/horario/<int:pk>/editar/', views_turnos.turnos_horario_editar, name='turnos_horario_editar'),
]