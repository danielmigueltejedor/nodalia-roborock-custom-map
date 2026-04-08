# Nodalia Roborock Custom Map

you MUST be on 2025.4b or later

This allows you to use the core Roborock integration with the [Xiaomi Map Card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card)

This fork also works well with `nodalia-advance-vacuum-card` and publishes richer map metadata:

- More frequent live map refresh while the robot is moving
- `vacuum_position`, `vacuum_room`, `vacuum_room_name` and `map_dimensions`
- Real room polygons extracted from the Roborock map pixels via `rooms[*].outlines`
- Rectangle fallbacks for cards that only understand simple room bounds

### Setup

1. Install the [Roborock Core Integration](https://my.home-assistant.io/redirect/config_flow_start?domain=roborock) and set it up
2. It is recommended that you first disable the Image entities within the core integration. Open each image entity, hit the gear icon, then trigger the toggle by enabled.
3. Install this integration(See the installing via HACS section below)
4. This integration works by piggybacking off of the Core integration, so the Core integration will do all the data updating to help prevent rate-limits. But that means that the core integration must be setup and loaded first. If you run into any issues, make sure the Roborock integration is loaded first, and then reload this one.
5. Setup the map card like normal! An example configuration would look like
```yaml
type: custom:xiaomi-vacuum-map-card
vacuum_platform: Roborock
entity: vacuum.s7
map_source:
  camera: image.s7_downstairs_full_custom
calibration_source:
  camera: true
```
For `nodalia-advance-vacuum-card`, an example configuration would look like:
```yaml
type: custom:nodalia-advance-vacuum-card
entity: vacuum.s7
map_source:
  image: image.s7_downstairs_full_custom
calibration_source:
  camera: true
```
6. You can hit Edit on the card and then Generate Room Configs to allow for cleaning of rooms. It might generate extra keys, so check the yaml and make sure there are no extra 'predefined_sections'

### Installation

### Installing via HACS
1. Go to HACS->Integrations
1. Add this repository as a custom repository in HACS
1. Search for Nodalia Roborock Custom Map and Download it
1. Restart your HomeAssistant
1. Go to Settings->Devices & Services
1. Add the Nodalia Roborock Custom Map integration

### Alternative/optional

Once you set up this integration, you can generate a static config in the lovelace card, and theoretically, you should be able to use that code with your Roborock CORE integration. However, it wont stay up to date if the map calibrations change significantly, or rooms change. So I'd only do this when I was sure everything was good!
