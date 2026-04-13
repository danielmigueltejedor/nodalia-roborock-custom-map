# 🗺️ Nodalia Roborock Custom Map

![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.1%2B-41BDF5?logo=home-assistant)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-stable-success.svg)
![GitHub](https://img.shields.io/badge/hosted%20on-GitHub-black?logo=github)

Integración personalizada para Home Assistant que permite usar la integración principal de Roborock con la [Xiaomi Map Card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card).  
Esta versión fork funciona perfectamente con `nodalia-advance-vacuum-card` y publica metadatos de mapa más ricos.

> 🟡 Proyecto no afiliado a Home Assistant ni a Roborock.  
> Uso personal y educativo.

---

## ✨ Características

- Actualización de mapa en vivo más frecuente mientras el robot se mueve
- Metadatos adicionales: `vacuum_position`, `vacuum_room`, `vacuum_room_name` y `map_dimensions`
- Polígonos reales de habitaciones extraídos de los píxeles del mapa de Roborock vía `rooms[*].outlines`
- Retrocesos rectangulares para tarjetas que solo entienden límites simples de habitaciones

---

## 🧩 Instalación

### 🔹 Opción 1 — HACS (Recomendada)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=danielmigueltejedor&repository=nodalia-roborock-custom-map&category=Integration)

---

## ⚙️ Configuración

1. Instala la [Integración Principal de Roborock](https://my.home-assistant.io/redirect/config_flow_start?domain=roborock) y configúrala
2. Se recomienda desactivar primero las entidades de Imagen en la integración principal. Abre cada entidad de imagen, haz clic en el icono de engranaje y desactiva el toggle.
3. Instala esta integración (ver sección de instalación vía HACS arriba)
4. Esta integración funciona aprovechando la integración principal, por lo que la integración principal debe estar configurada y cargada primero. Si encuentras problemas, asegúrate de que la integración de Roborock se cargue primero y luego recarga esta.
5. Configura la tarjeta de mapa como de costumbre. Un ejemplo de configuración sería:
```yaml
type: custom:xiaomi-vacuum-map-card
vacuum_platform: Roborock
entity: vacuum.s7
map_source:
  camera: image.s7_downstairs_full_custom
calibration_source:
  camera: true
```
Para `nodalia-advance-vacuum-card`, un ejemplo de configuración sería:
```yaml
type: custom:nodalia-advance-vacuum-card
entity: vacuum.s7
map_source:
  image: image.s7_downstairs_full_custom
calibration_source:
  camera: true
```
6. Puedes hacer clic en Editar en la tarjeta y luego Generar Configs de Habitaciones para permitir la limpieza de habitaciones. Puede generar claves extra, así que revisa el YAML y asegúrate de que no haya 'predefined_sections' extra.

### Alternativa opcional

Una vez configurada esta integración, puedes generar una configuración estática en la tarjeta de Lovelace, y teóricamente podrías usar ese código con tu integración de Roborock CORE. Sin embargo, no se mantendrá actualizada si las calibraciones del mapa cambian significativamente o las habitaciones cambian. Así que solo haz esto cuando estés seguro de que todo está bien.

---

## 🧠 Detalles técnicos

- Debes estar en Home Assistant 2025.4b o superior
- La integración se basa en la integración principal de Roborock para evitar límites de tasa
- Metadatos enriquecidos para compatibilidad con tarjetas avanzadas de mapas

---

## 🧑‍💻 Autor

- **[@danielmigueltejedor](https://github.com/danielmigueltejedor)**  
- Repositorio: https://github.com/danielmigueltejedor/nodalia-roborock-custom-map  
- Licencia: MIT

---

## 💰 Donaciones

Si te gusta este proyecto y quieres apoyar su desarrollo, considera hacer una donación:

[![PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg)](https://paypal.me/DanielMiguelTejedor)
