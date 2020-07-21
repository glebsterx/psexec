"""
Компонент добавляет службу `psexec.exec` удаленного выполнения команд на
компьютерах Windows через протокол `SMB 2`. В момент выполнения на удалённом
компьютере создаётся и запускается служба Windows, выполняющая указанную
команду. По завершению выполнения служба удаляется.

Удалённый пользователь должен быть администратором.

Если на удалённом компьютере включен UAC - необходимо внести правки в реестр:

```
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System]
"LocalAccountTokenFilterPolicy"=dword:00000001
```

Если удалённый Windows старый (например win7) - необходимо указывать параметр
`encrypt=false`.

Подробности тут: https://pypi.org/project/pypsexec/

Пример использования (создаст в корне диска C файл out.txt):

```
script:
  smb_remote:
    sequence:
    - service: psexec.exec
      data:
        host: 192.168.1.123
        username: user
        password: pass
        encrypt: false
        command: cmd.exe /c echo Hello World > c:\out.txt
```

Для засыпания компьютера необходимо отправить команду:

```
cmd.exe /c start /b shutdown.exe /h
```

- `cmd.exe /c` - выполняет далее указанную команду (для start нет exe файла)
- `start /b` - запускает следующую команду в фоне (нельзя дожидаться окончания
  выполнения shutdown - мы его не дождёмся)
- `shutdown.exe /h` - отправляет компьютер в сон (или гибернацию в зависимости
  от настроек компьютера)

Компонент протестирован в HA на Windows и в Hass.io на Raspberry Pi 3.

"""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "psexec"


def setup(hass, config):
    def exec(call):
        import uuid

        from smbprotocol.connection import Connection
        from smbprotocol.session import Session

        from pypsexec.scmr import Service

        host = call.data.get('host')
        username = call.data.get('username')
        password = call.data.get('password')
        encrypt = call.data.get('encrypt', True)

        command = call.data.get('command')

        try:
            connection = Connection(uuid.uuid4(), host)
            connection.connect()
            session = Session(connection, username, password,
                              require_encryption=encrypt)
            session.connect()
            service = Service('HomeAssistant', session)
            service.open()

            try:
                service.create(command)
            except:
                _LOGGER.exception("Can't create service")

            try:
                service.start()
            except:
                # Произвольный EXE-файл не может быть полноценной Службой,
                # поэтому даже при успешном выполнении мы будем получать ошибку
                pass

            try:
                service.delete()
            except:
                _LOGGER.exception("Can't delete service")

            service.close()
            connection.disconnect()

        except:
            _LOGGER.exception(f"Can't connect to: {host}")

    hass.services.register(DOMAIN, 'exec', exec)

    return True
