# spacedesk Linux (no oficial)

> HISTORICO: documentacion de la instalacion standalone anterior al panel GTK.
> Sus ejemplos de topologia no se usan como configuracion de la app actual.
> Consultar el README principal para instalar y elegir monitores.

Origen: https://github.com/jeromeollivon-star/spacedesk-linux
Commit: 9e0cdb7032dc1b1a0bcaea10358c41572324d69c
SHA256 original de spacedesk_client.py: ae167043448223c3044a892d1f2cf64299bef7b8433dd0f67bc3a776377b52c7
Cambio local: flag keepawake independiente por puerto dentro de XDG_RUNTIME_DIR.
Cambio local: ACK inicial y de paquetes de visibilidad, necesarios para recibir video del servidor.
Cambio local: identificacion UTF-16 completa desde el inicio del payload, sin prefijo numerico; UUID estable por equipo/monitor.
Cambio local: respuesta Pong con campo de respuesta 2 en offset 12, en lugar de eco del Ping.
Cambio local: ACK por imagen (cuatro fragmentos), sin pausa artificial; calidad JPEG 50.
Referencia independiente de identificacion/Pong: https://github.com/GregoireDelannoy/echoscreen/blob/8cc1bfa141da2e3f0ec10e8fa0e4809eef7b65a2/spacedesk_protocol.py

Documento historico; la IP se configura localmente y no se incluye en el proyecto.
Dos procesos independientes; no utiliza el visor HTML5 oficial ni Wine.
Cada proceso crea una pantalla en Windows al abrir su visor local.

Abrir desde aplicaciones: "spacedesk - Dos monitores Windows".
O ejecutar: python3 ~/.local/share/spacedesk-linux/launch.py --both
La opcion --monitor 1 o --monitor 2 abre solo el visor seleccionado.
Sin opciones se abre solo el primero. Los accesos individuales tambien estan disponibles.
Reabrir un visor ya conectado activa y posiciona su ventana existente, sin duplicarla.
Se usa GdkX11 para posicionar y poner en pantalla completa los visores en sus monitores reales.
Se deshabilito la reconexion automatica; una desconexion muestra un aviso y boton Reintentar.

Monitor 1: HDMI-A-1-3, 1920x1080, posición 0,0, http://127.0.0.1:8091/
Monitor 2: HDMI-2-1, 1366x768, posición 3840,0, http://127.0.0.1:8092/
El monitor principal HDMI-0 queda para Linux.

Cerrar ambas ventanas desconecta las pantallas de Windows.
Para cerrar todo: python3 ~/.local/share/spacedesk-linux/launch.py --stop
O usar "spacedesk - Cerrar pantallas" en Aplicaciones.
Detener servicios: systemctl --user stop spacedesk-monitor@1 spacedesk-monitor@2
Ver registros: journalctl --user -u 'spacedesk-monitor@*' -n 50

No se habilita inicio automático ni se exponen los visores a la red.
El cliente es experimental; entrada de teclado local no implementada por upstream.
Usar el teclado y mouse de Windows para trabajar normalmente.

Estado de verificacion: ambos monitores recibieron JPEG simultaneamente durante mas de 130 segundos,
sin cierres del servidor y con respuestas de mantenimiento correctas. Ambos visores reales
verificados en estado streaming, con una unica ventana por monitor y geometria fullscreen correcta.
La identificacion anterior empezaba con U+0001 seguido de NUL, ocultando GUID/nombre al parser de cadenas.
Las correcciones de identificacion, Pong y ACK se validaron juntas; no se hizo ablacion de cada cambio.

Pruebas locales sin conectar a Windows:
python3 ~/.local/share/spacedesk-linux/test_client.py -v

Prueba de protocolo (crea dos pantallas temporales en Windows; cerrar primero los visores):
python3 ~/.local/share/spacedesk-linux/test_protocol.py --dual --seconds 130

Estado local, sin crear conexiones nuevas al driver:
curl http://127.0.0.1:8091/status
curl http://127.0.0.1:8092/status
