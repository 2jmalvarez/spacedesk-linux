# Attribution / provenance

This project is **unofficial** and is not affiliated with Datronicsoft or spacedesk.
The Windows driver and the spacedesk name belong to their respective owners.
No proprietary Windows installer or driver is distributed here.

## Original Python bridge

`src/spacedesk_linux/bridge.py` derives from:

- https://github.com/jeromeollivon-star/spacedesk-linux
- Commit: `9e0cdb7032dc1b1a0bcaea10358c41572324d69c`
- Original SHA-256: `ae167043448223c3044a892d1f2cf64299bef7b8433dd0f67bc3a776377b52c7`
- MIT license, Copyright (c) 2026 Jerome Ollivon; license retained in `LICENSE`.

Local modifications include correct UTF-16 client identification, Pong responses,
frame acknowledgements, stable identities, connection status, user-controlled
retry, serialized socket writes, explicit Disconnect/ordered signal shutdown,
local HTTP origin checks and per-instance runtime flags.

## Independent protocol reference

Identification/Pong behavior was compared with this independently implemented client:

https://github.com/GregoireDelannoy/echoscreen/blob/8cc1bfa141da2e3f0ec10e8fa0e4809eef7b65a2/spacedesk_protocol.py

The controller, GUI, configuration, packaging and tests are local additions.
`docs/legacy-launch.py` and `docs/legacy-installation.md` preserve the earlier
standalone launcher and its technical history; they are not the installed app.
