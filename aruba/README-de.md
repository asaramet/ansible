# Aruba Switch Network Administration mit Ansible

Dieses Projekt bietet Ansible Inventory und Playbooks, die speziell für die Netzwerkverwaltung von Aruba-Switches konzipiert sind. Es basiert auf der [AOS-CX Ansible Collection](https://developer.arubanetworks.com/aruba-aoscx/docs/getting-started-with-ansible-and-aos-cx)

## Inhaltsverzeichnis

- [AOS-CX Ansible Collection](#aos-cx-ansible-collection)
- [Kontrolknotten](#kontrollknoten)
- [Inventar](#inventar)
- [Playbooks](#playbooks)
  - [Sicherung der Switch-Konfiguration](#sicherung-der-switch-konfiguration)
  - [Day 0 Switch-Konfiguration](#day-0-switch-konfiguration)
  - [Show-Befehle auf Switch ausführen](#show-befehle)
  - [Switch-Firmware hochladen](#switch-firmware-hochladen)
- [Lizenz](#lizenz)
- [Anmerkungen](#anerkennungen)

## AOS-CX Ansible Collection

In Ansible sind Collections dazu gedacht, Inhalte aufzubauen und zu verteilen, die Playbooks, Rollen, Module und Plugins enthalten können. Standard- und Benutzersammlungen können über einen Vertriebsserver wie Ansible Galaxy installiert werden.

Die offiziellen Aruba Ansible AOS-CX-Module sind in der [AOS-CX Ansible Collection](https://developer.arubanetworks.com/aruba-aoscx/docs/using-the-aos-cx-ansible-collection) gepackt und werden auf einem öffentlichen [GitHub-Repository](https://github.com/aruba/aoscx-ansible-collection) gehostet.

Der Ansible Galaxy-Verteilungsserver ist ein nützliches Tool zum Installieren und Verwalten der Sammlung.

### Installieren der AOS-CX-Sammlung mit dem Ansible Galaxy-Verteilungstool

1. Überprüfen Sie den richtigen Pfad zum `collections`-Ordner:

    ```bash
    ansible-galaxy collection list

    # /opt/ansible/lib/python3.9/site-packages/ansible_collections
    Collection                    Version
    ----------------------------- -------
    ....
    ```

2. Installieren Sie die Sammlung:

    ```bash
    ansible-galaxy collection install arubanetworks.aoscx -p /opt/ansible/lib/python3.9/site-packages/ansible_collections 
    ```

3. Aktualisieren Sie die Sammlung:

    ```bash
    ansible-galaxy collection install -U arubanetworks.aoscx -p /opt/ansible/lib/python3.9/site-packages/ansible_collections 
    ```

## Kontrollknoten

Der Kontrollknoten ist der Computer, von dem aus die Ansible CLI-Tools wie `ansible`, `ansible-playbook`, `ansible-inventory` usw. ausgeführt werden. In unserer Umgebung verwenden wir eine virtuelle Linux-Maschine mit dem Hostnamen `rhlx0023` als unseren Kontrollknoten.

Um Ansible auf diesem Computer zu verwenden, haben wir eine Python-Sandbox mit dem Ansible-Paket und allen notwendigen Anforderungen unter `/opt/ansible` konfiguriert. Um diese Einrichtung zu nutzen, sollten Sie die in der `envs`-Datei definierten Umgebungsvariablen in Ihrer Bash-Shell aktivieren. Sie können dies tun, indem Sie den folgenden Befehl ausführen:

```bash
rhlx0023 $ source /opt/ansible/envs
```

Dies stellt sicher, dass Ansible-Befehle mit den richtigen Umgebungsvariablen ausgeführt werden und Sie Ihre Infrastruktur effizient verwalten können.

## Inventar

Dieses Ansible-Inventar enthält Switches, die in `sm_6100` und `hze_6100` wieder gruppiert sind in -> `aruba_6100` -> `aruba` groups. Linux-Manager-Server befinden sich in der Gruppe `linux`. Empfindliche Daten wie Passwörter werden mit `ansible-vault` in `host_vars/host/vault` gespeichert.

Verwenden Sie den folgenden Befehl, um das Inventar anzuzeigen:

```bash
ansible-inventory --graph
```

Für eine detailliertere Ausgabe mit Variablen verwenden Sie:

```bash
ansible-inventory --graph --vars
```

## Playbooks

Ansible Playbooks ermöglichen die wiederholbare Ausführung von vordefinierten Ansible-Befehlen über mehrere Hosts, was ein einfaches Konfigurations-, Multi-Maschinen-Management-, Wartungs- und Bereitstellungssystem bietet.

Folgende Playbooks sind in diesem Repository enthalten:

Um ein Playbook auszuführen, verwenden Sie den folgenden Befehl:

```bash
ansible-playbook [OPTIONS] playbook-name.yaml

# Zum Beispiel, um das show.yaml-Playbook in diesem Inventar auszuführen:
ansible-playbook playbooks/show.yaml
```

### Sicherung der Switch-Konfiguration

Datei: `playbooks/backup_config.yaml`

Diese Ansible-Playbook-Datei ist darauf ausgelegt, zwei Hauptaufgaben auszuführen: die Sicherung der Laufkonfiguration von Aruba-Switches, die unter der Hostgruppe `aruba` angegeben sind, und das Kopieren der resultierenden Konfigurationsdateien auf eine Remote-Maschine, die unter der Hostgruppe `rhlx99` angegeben ist.

Die erste Aufgabe mit dem Titel "Sichern der 'running-config' in einem lokalen Ordner" wird auf den `aruba`-Hosts ausgeführt und nutzt die Aruba Networks AOS-CX Collection. Das Playbook erstellt einen neuen Unterordner innerhalb eines angegebenen Arbeitsverzeichnisses, benannt nach der Gruppe, zu der jeder Switch gehört. Anschließend sichert es die Laufkonfiguration jedes Switches in den entsprechenden Gruppenunterordner.

Die zweite Aufgabe mit dem Titel "Kopieren von Konfigurationsdateien auf rhlx99" wird auf dem `rhlx99`-Host ausgeführt und beinhaltet das Kopieren der zuvor gesicherten Konfigurationsdateien aus dem lokalen Verzeichnis in das `tftpboot/`-Verzeichnis der Remote-Maschine. Das Playbook nutzt das `copy`-Modul, um dies zu erreichen, und setzt die notwendigen Dateiberechtigungen und Eigentümerschaften.

Insgesamt kann dieses Playbook genutzt werden, um Netzwerkkonfigurationsmanagement-Aufgaben zu vereinfachen, indem die Sicherung und Übertragung von Konfigurationsdateien über mehrere Aruba-Switches und eine Remote-Maschine automatisiert wird.

### Day 0 Switch-Konfiguration

Datei: `playbooks/day_0_config.yaml`

Dieses Playbook hat drei Hauptabschnitte:

1. Globale Variablen festlegen: Dieser Abschnitt definiert eine globale Variable `work_dir`, die über einen YAML-Anker und Alias auf `/opt/ansible/inventories/aruba/` gesetzt wird. Es wird auf dem Host `localhost` ausgeführt.

2. Generieren einer Konfigurationsdatei für Aruba-6100-Switches aus einer Jinja-Vorlage: Dieser Abschnitt wird auf den Hosts `new_6100` ausgeführt und generiert eine Konfigurationsdatei aus einer Jinja2-Vorlage. Es erstellt für jede Hostgruppe einen Unterordner in `work_dir` und speichert die generierte Datei in diesem Unterordner mit dem Hostnamen als Dateinamen.

3. Kopieren der generierten Konfigurationsdateien auf einen Linux-Server und Hochladen der Konfiguration auf die Switches: Diese beiden Abschnitte werden auf den Hosts `rhlx99` und `new_6100` ausgeführt. Der Abschnitt `rhlx99` kopiert die generierten Konfigurationsdateien in das Verzeichnis `/tftpboot/` auf dem Host `rhlx99`, und der Abschnitt `new_6100` lädt die Konfigurationsdatei auf jeden `new_6100`-Host hoch, indem er das Modul `aoscx_config` aus der Sammlung `arubanetworks.aoscx` verwendet.

Insgesamt generiert dieses Playbook Konfigurationsdateien für Aruba-6100-Switches, kopiert sie auf einen Linux-Server und lädt sie dann auf die entsprechenden Switches hoch.

### Show Befehle

Datei: `playbooks/show.yaml`

Dieses Ansible-Playbook ist dafür ausgelegt, eine Reihe von `show`-Befehlen auf allen Aruba-Switches auszuführen, die unter der Host-Gruppe `aruba` aufgeführt sind. Das Playbook nutzt die Aruba Networks AOS-CX Collection und setzt die Variable `ansible_connection` auf `network_cli`. Das Playbook führt beispielsweise den `show vlan`-Befehl auf dem Switch aus und registriert die Ausgabe in einer Variable namens `show_vlan_output`. Schließlich gibt das Playbook die standardmäßige Ausgabe mit dem `debug`-Modul und der Variablen `show_vlan_output.stdout` aus.

Insgesamt kann dieses Playbook verwendet werden, um schnell Informationen zur VLAN-Konfiguration auf mehreren Aruba-Switches abzurufen und so die Netzwerkverwaltung und Fehlerbehebung zu optimieren.

### Switch Firmware hochladen

Datei: `playbooks/6100_upload_firmware.yaml`

Dieses Playbook ist für das Aktualisieren der Firmware auf Aruba 6100-Switches über CLI-Befehle konzipiert. Hier ist eine Aufschlüsselung der verschiedenen Aufgaben:

1. Gruppensubordner erstellen: Diese Aufgabe erstellt einen Unterordner für die Switches in der Inventargruppe, falls er noch nicht vorhanden ist.

2. Backup erstellen und aktuelle Konfiguration in der Startkonfiguration speichern: Diese Aufgabe verwendet das `aoscx_config`-Modul, um die aktuelle Running-Konfiguration in die Datei `startup-config` zu sichern.

3. Firmware auf primärer Partition hochladen: Diese Aufgabe lädt die Firmware-Datei auf die primäre Partition mit dem `aoscx_config`-Modul hoch. Der vorherige Abschnitt des Moduls wird verwendet, um die primäre Partition vor dem Firmware-Upload auf die sekundäre Partition zu sichern.

4. Booten in die primäre Partition: Diese Aufgabe startet den Switch in die primäre Partition mit dem aoscx_boot_firmware-Modul.

Insgesamt sollte dieses Playbook wie vorgesehen funktionieren, um die Firmware auf Aruba 6100-Switches zu aktualisieren.

## Lizenz

Dieses Projekt steht unter der MIT-Lizenz. Weitere Informationen finden Sie in der Datei LICENSE.md.

## Anerkennungen

Dieses Projekt verwendet die folgenden Ressourcen von Drittanbietern:

- [Ansible](https://www.ansible.com) - zur Konfigurationsverwaltung und Automatisierung von Aruba-Switches
- [GitHub](https://github.com) - für Quellcode-Hosting und Kollaborationstools
