# spacedesk Linux Control

[![Tests](https://github.com/2jmalvarez/spacedesk-linux/actions/workflows/tests.yml/badge.svg)](https://github.com/2jmalvarez/spacedesk-linux/actions/workflows/tests.yml)

**Usá los monitores conectados a tu PC Linux como pantallas adicionales de otra PC Windows.**

Panel gráfico sencillo para elegir **qué monitores usar, cuántos y con qué resolución**.
Linux sigue funcionando normalmente en las pantallas que no selecciones.

> **Proyecto no oficial y experimental**, sin afiliación con Datronicsoft.
> No reemplaza el driver spacedesk de Windows. Esta versión necesita **Linux/X11**;
> **Wayland no está soportado**.

## Qué hace

- Detecta monitores activos, conectores, posiciones y resoluciones disponibles.
- Muestra un mapa seleccionable y permite identificar cada monitor físicamente.
- Permite elegir desde cero hasta la cantidad de pantallas detectadas.
- Configura resolución independiente por pantalla, con opción **Nativa**.
- Guarda la IP de Windows, la selección y la calidad de imagen.
- Abre un visor en pantalla completa sobre cada destino elegido, sin duplicados.
- Muestra estados de conexión y errores; no entra en bucles de reconexión.
- Un solo botón alterna entre **Conectar** y **Desconectar** según el estado real.
- Visor en español, sin sugerencias automáticas de traducción de Chrome.
- Actualiza la lista al conectar/quitar monitores, además del botón **Actualizar**.
- Al desconectar, avisa al driver de Windows antes de cerrar la conexión.

Ejemplo: si tenés dos monitores grandes y uno pequeño, podés dedicar los dos
grandes a Windows y dejar el pequeño para Linux y este panel de control.

## Cómo funciona

```text
PC Windows: aplicaciones + escritorio extendido
                    |
            spacedesk DRIVER
                    |
          TCP 28252, red local
                    |
PC Linux: un puente Python independiente por pantalla
                    |
       HTTP/WebSocket solo en 127.0.0.1
                    |
        Chrome/Chromium en pantalla completa
                    |
         Monitores físicos seleccionados

Panel GTK -> configuración, servicios, ventanas y estado
```

El driver de Windows crea las pantallas virtuales y envía la imagen dividida en
fragmentos JPEG. Cada puente Python reconstruye el flujo para su visor local y
confirma las imágenes recibidas. Los mensajes de mantenimiento mantienen la sesión.

Cada pantalla tiene una identidad estable, un puerto local y un perfil de navegador
propios. El controlador usa servicios **systemd por usuario** y GdkX11 para colocar
las ventanas en los monitores correctos. No necesita Wine ni Docker.

**El panel elige dónde se ve cada pantalla en Linux.** El orden lógico del escritorio
de Windows —por dónde pasa el mouse de una pantalla a otra— se configura en
**Windows → Configuración → Sistema → Pantalla**.

## Requisitos

### En Windows

1. Instalar el **spacedesk DRIVER** desde [la web oficial](https://www.spacedesk.net/download/).
2. Dejar habilitado el servidor en su consola.
3. Conectar Windows y Linux a la misma red local o a una red en la que puedan comunicarse.
4. Permitir spacedesk en el firewall de Windows para la red utilizada; se necesita TCP 28252.
5. Anotar la IPv4 del equipo Windows para ingresarla en el panel Linux.

No instalar este proyecto en Windows: **Windows es el servidor y Linux es el receptor**.
Esta implementación todavía no soporta conexiones que exijan contraseña.

### En Linux

Entorno gráfico probado: **Ubuntu 24.04, GNOME/X11, Python 3.12 y GTK 3.24**.
Las pruebas sin interfaz también se ejecutan en CI con Python 3.10, 3.12 y 3.13.

- Sesión **X11/Xorg**, no Wayland.
- Python 3.10 o posterior, PyGObject, GTK 3 y GdkX11.
- `xrandr`, `xprop` y servicios `systemctl --user` funcionando.
- **Google Chrome**, recomendado y probado, o Chromium compatible con perfiles personalizados.
- Se recomienda Ethernet; Wi-Fi también puede funcionar, con mayor latencia o consumo de red.

No hace falta desinstalar GTK 4 si está presente: la app selecciona explícitamente GTK/Gdk 3.
Chrome/Chromium en Snap o Flatpak no están validados; su aislamiento puede impedir
usar los perfiles personalizados o identificar las ventanas.

## Instalar en una PC Linux nueva

### 1. Iniciar una sesión X11

En Ubuntu, cerrar sesión y elegir **Ubuntu en Xorg** en las opciones de la pantalla
de inicio de sesión, si esa opción está disponible. Podés verificar la sesión con:

```bash
echo "$XDG_SESSION_TYPE"
```

Debe indicar `x11`. Instalar estas dependencias **no agrega soporte para Wayland**.

### 2. Instalar dependencias

En Ubuntu:

```bash
sudo apt update
sudo apt install git python3 python3-gi gir1.2-gtk-3.0 x11-xserver-utils x11-utils
```

Instalar además Google Chrome desde [su sitio oficial](https://www.google.com/chrome/),
si no está instalado. El script de este proyecto no instala navegadores ni paquetes
del sistema. Otras distribuciones necesitan los paquetes equivalentes y systemd por usuario.

### 3. Descargar e instalar la app

```bash
git clone https://github.com/2jmalvarez/spacedesk-linux.git
cd spacedesk-linux
./scripts/install-user.sh
```

El instalador trabaja **solo para tu usuario, sin sudo**. Copia el código, genera
los accesos de Aplicaciones y el servicio plantilla. No cambia Windows, no modifica
la disposición de Linux y no conecta pantallas automáticamente.

También podés copiar la carpeta completa del proyecto desde otra PC y ejecutar el
mismo script; no es obligatorio usar Git. **No copies la configuración privada ni
los perfiles del navegador de la otra PC.**

### 4. Abrir y conectar

Abrir **Aplicaciones → spacedesk Linux**, o ejecutar:

```bash
~/.local/bin/spacedesk-linux
```

1. Ingresar la IP/nombre del equipo Windows.
2. Usar **Identificar** para reconocer los monitores.
3. Seleccionar los destinos en el mapa o con las casillas.
4. Elegir cantidad, resoluciones y calidad JPEG.
5. Pulsar **Conectar**.
6. En Windows, elegir **Extender estas pantallas** si fuera necesario y ordenar su disposición.

**Guardar configuración** conserva preferencias, pero no aplica los cambios a las
conexiones actuales. El único botón de conexión muestra **Conectar** cuando no hay
pantallas activas y **Desconectar** cuando hay alguna conectada o en proceso de
conexión. Mientras procesa una operación queda deshabilitado para evitar dobles clics.
Para aplicar cambios a una sesión activa, pulsar **Desconectar** y luego **Conectar**.
Cerrar el panel deja los visores abiertos; **Desconectar** detiene las pantallas de
Windows y cierra solo los navegadores aislados de esta app.

La página del visor declara español y evita traducción automática. Además, al abrir
un visor se desactiva la sugerencia de traducción en su perfil aislado. **No se cambia
la configuración de tu Chrome habitual** ni se alteran perfiles mientras están abiertos.

## Detección y selección de monitores

En el primer inicio se preseleccionan hasta **dos monitores de mayor resolución nativa**;
con uno solo, se selecciona uno. No se excluye el principal de Linux automáticamente.
Podés elegir cualquier combinación y guardar otra preferencia.

Los destinos se recuerdan por **conector**, no por el número de enumeración ni por
coordenadas escritas en el código. Las posiciones actuales se vuelven a detectar.
Si falta un destino guardado, la app informa el problema al intentar conectar:
**no lo reemplaza silenciosamente por otro**.

Al enchufar/quitar un monitor, el panel actualiza la lista tras una pausa breve.
Los monitores nuevos aparecen deseleccionados y **no se conectan por sí solos**.
**Actualizar** permite forzar una nueva detección. Para evitar que el escritorio de
Linux reubique un visor activo, desconectalo antes de quitar físicamente su monitor.

La resolución elegida corresponde a la pantalla virtual de Windows. No cambia el
modo físico de Linux. **Nativa** utiliza la resolución preferida anunciada por el monitor.
La calidad JPEG controla compresión/nitidez, no la cantidad de píxeles; más calidad
consume más red y puede reducir la fluidez.

## Desconexión ordenada

Al cerrar el último visor de una pantalla o detener su servicio, el puente envía el
paquete de protocolo **Disconnect**, termina la escritura TCP y cierra con esperas
acotadas. También maneja `SIGTERM`/`SIGINT`, por lo que `systemctl stop` no omite esa
limpieza. Al desconectar varias pantallas, sus servicios se detienen en paralelo.

Esto evita depender únicamente del timeout del servidor para notificar el cierre.
El tiempo visible de reacomodo del escritorio todavía depende del driver y de Windows:
no se garantiza una duración exacta. Si la red se corta o el proceso es terminado
forzosamente, el servidor puede tener que detectar la pérdida por timeout.

## Comandos de terminal

```bash
spacedesk-linux gui       # Abrir el panel
spacedesk-linux connect   # Conectar la selección guardada
spacedesk-linux stop      # Desconectar todos los visores
spacedesk-linux status    # Consultar estado por pantalla
spacedesk-linux displays  # Ver monitores activos y modos disponibles
```

Si `~/.local/bin` no está en PATH, anteponer esa ruta a cada comando.

## Actualizar o migrar una instalación anterior

Cerrar el panel, detener los visores y actualizar la copia instalada:

```bash
~/.local/bin/spacedesk-linux stop
git pull --ff-only
./scripts/install-user.sh
~/.local/bin/spacedesk-linux
```

El instalador conserva la configuración existente. No basta con `git pull`: los
servicios ejecutan una copia instalada, no los archivos del checkout.

Para migrar el prototipo standalone anterior a esta app:

```bash
./scripts/install-user.sh --migrate-legacy
```

La migración respalda los archivos anteriores en
`~/.local/state/spacedesk-linux/backups/` antes de detener sus visores. Los antiguos
comandos `launch.py --both` y `launch.py --stop` quedan como accesos de compatibilidad.

## Ubicación de archivos y privacidad

| Contenido | Ubicación predeterminada |
|---|---|
| Código instalado | `~/.local/share/spacedesk-linux/app/` |
| Configuración privada | `~/.config/spacedesk-linux/config.json` |
| Entornos generados por pantalla | `~/.config/spacedesk-linux/runtime/` |
| Perfiles de navegador y registros | `~/.cache/spacedesk-linux/` |
| Servicio por pantalla | `spacedesk-linux@<id>.service` |

Se respetan los directorios XDG. El repositorio no contiene una IP personal,
credenciales, perfiles de Chrome, registros ni instaladores propietarios.

Los servidores HTTP/WebSocket solo escuchan en `127.0.0.1` y validan el host/origen
de las solicitudes. El transporte actual hacia Windows **no está cifrado** y no
hay autenticación implementada: usar únicamente una red confiable. **No abrir
puertos hacia Internet ni utilizar esta app en redes no confiables.**

## Solución de problemas

| Problema | Qué revisar |
|---|---|
| Sesión Wayland | Iniciar X11/Xorg; no basta con tener `xrandr` instalado. |
| No aparece un monitor | Activarlo primero en Linux y pulsar Actualizar. Solo se listan salidas activas. |
| Windows no envía imagen | IP, conectividad, consola spacedesk y firewall TCP 28252. |
| Pantallas duplicadas en Windows | Elegir Extender, no Duplicar, en la configuración de Windows. |
| Destino guardado no disponible | Revisar el cable/conector o cambiar la selección; no se reasigna automáticamente. |
| Se ve borroso | Usar Nativa y aumentar calidad JPEG; comprobar también el escalado de Windows. |
| Va lento | Probar Ethernet, bajar calidad o resolución y revisar carga/red de Windows. |
| Puerto local ocupado | Detener una instalación anterior u otra aplicación que use el puerto. |
| No abre el navegador | Probar Google Chrome instalado de forma nativa y revisar registros. |
| Windows tarda en retirar pantallas | Actualizar/reinstalar y reiniciar los visores; un proceso viejo no incorpora el cierre ordenado. |

Para consultar registros:

```bash
journalctl --user -u 'spacedesk-linux@*' -n 100 --no-pager
~/.local/bin/spacedesk-linux status
```

## Desarrollo y pruebas

```text
src/spacedesk_linux/   GUI, configuración, detección, controlador y protocolo
packaging/            Plantillas systemd y accesos de escritorio
scripts/              Instalación, desinstalación y diagnóstico de protocolo
tests/                Pruebas unitarias, GTK y servidor local simulado
docs/                 Historia y código del prototipo standalone
```

Ejecutar desde el checkout:

```bash
PYTHONPATH=src /usr/bin/python3 -m spacedesk_linux gui
PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
```

Pruebas GTK opcionales en una sesión X11 real; abren y cierran un panel de prueba,
sin guardar preferencias ni conectar a Windows:

```bash
SPACEDESK_TEST_GUI=1 PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
```

La suite incluye un servidor Windows **simulado en localhost** para comprobar que
cerrar un visor y enviar `SIGTERM` emiten Disconnect y no bloquean el servidor HTTP.
GitHub Actions ejecuta las pruebas sin GUI con Python 3.10, 3.12 y 3.13.

Para una prueba real del protocolo, cerrar primero los visores:

```bash
~/.local/bin/spacedesk-linux stop
/usr/bin/python3 scripts/test_protocol.py --seconds 130
```

Esta última prueba **crea pantallas temporales en Windows**, usa la configuración
local y rechaza ejecutarse si ya hay visores activos para no competir por sus identidades.

## Desinstalar

Desde el checkout:

```bash
./scripts/uninstall-user.sh
```

Detiene los servicios y elimina el paquete y los accesos instalados. Conserva la
configuración, caché y respaldos; no borra el checkout ni el navegador habitual.

## Limitaciones y licencia

- Cliente no oficial: futuras versiones del driver pueden cambiar el protocolo.
- X11 solamente; no soporte de Wayland, audio o autenticación por contraseña.
- El teclado local no se reenvía. Usar el teclado/mouse del equipo Windows para trabajar.
- No se habilita conexión ni inicio automático al iniciar sesión.
- No se distribuye ni instala el driver propietario de Windows.

Licencia **MIT**. Se conserva la licencia del repositorio y la atribución del puente
original. Ver [LICENSE](LICENSE) y [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
para autores, procedencia y modificaciones.
