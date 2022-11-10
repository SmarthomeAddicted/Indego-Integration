# Indego-Integration

## Installation
Kopiere den Ordner `indego` in den `custom_components` Ordner von Home Asstiant.

## Konfiguration
Füge deine Domäne zu deiner `configuration.yaml` hinzu. Benutzername, Passwort und ID (serial) sind verpflichtend. Der Name ist optional (Standard = Indego).
```YAML 
#configuration.yaml
indego:
  username: !secret indego_username
  password: !secret indego_password
  id:       !secret indego_id
#Optional
  name:     Indego
```
Füge deine in der Bosch Indego App verwendeten Anmeldedaten (E-Mail-Adresse, Passwort und Seriennummer des Mähers) zu deiner `secrets.yaml` hinzu:
```YAML 
#secrets.yaml
indego_username: "name@mail.com"
indego_password: "mysecretpw"
indego_id:       "123456789"
```

## Neustart

Starte dein HA neu, damit HA die neu hinzugefügten Entitäten findet.



## Credits

Thanks to jm-73 

Diese Integration basiert auf folgender Integration und wurde erweitert, sodass alle Daten von dem Mähroboter in HA verfügabar sind inkl. der Karte.  https://github.com/jm-73/Indego

