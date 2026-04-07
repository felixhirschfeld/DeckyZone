# DeckyZone

[![](https://img.shields.io/github/downloads/DeckFilter/DeckyZone/total.svg)](https://github.com/DeckFilter/DeckyZone/releases)
[![](https://img.shields.io/github/downloads/DeckFilter/DeckyZone/latest/total)](https://github.com/DeckFilter/DeckyZone/releases/latest)
[![](https://img.shields.io/github/v/release/DeckFilter/DeckyZone)](https://github.com/DeckFilter/DeckyZone/releases/latest)

DeckyZone is a Decky plugin for the Zotac Gaming Zone that aims to bridge the most common compatibility gaps until full compatibility lands. I started with controller-related fixes first, because those were the first issues I ran into and I was especially hyped about getting the dials working.

![screenshot](./img/DeckyZone.jpg)

## Current Features

### Controller

| Feature                      | SteamOS `main` | Bazzite | Nobara | CachyOS |
| ---------------------------- | -------------- | ------- | ------ | ------- |
| Enable Controller Features   | ✅             | ❌      | ❓     | ❓      |
| Enable Home Button           | ✅             | ❌      | ❓     | ❓      |
| Enable Brightness Dial       | ✅             | ❌      | ❓     | ❓      |
| Vibration / Rumble Intensity | ✅             | ✅      | ❓     | ❓      |
| Test Rumble                  | ✅             | ❌      | ❓     | ❓      |
| Enable Per-Game Settings     | ✅             | ❌      | ❓     | ❓      |
| Button Prompt Fix            | ✅             | ❌      | ❓     | ❓      |
| Disable Trackpads            | ✅             | ❌      | ❓     | ❓      |

### Interface

| Feature             | SteamOS `main` | Bazzite | Nobara | CachyOS |
| ------------------- | -------------- | ------- | ------ | ------- |
| Enable Zotac Glyphs | ✅             | ❓      | ❓     | ❓      |

### Display

| Feature                   | SteamOS `main` | Bazzite | Nobara | CachyOS |
| ------------------------- | -------------- | ------- | ------ | ------- |
| Enable Zotac OLED Profile | Built in       | ✅      | ❓     | ❓      |
| Enable Green Tint Fix     | ✅             | ✅      | ❓     | ❓      |

`HDR / Washed out colors` is fixed out of the box on the latest SteamOS `main` and on the `SteamOS 3.8.1 Preview`. Was also fine on Bazzite, Nobara and CachyOS.

Controller features rely on InputPlumber. Bazzite will soon switch to InputPlumber. Nobara did not work with Decky Loader but it has InputPlumber ootb and CachyOS needs to install InputPlumber manually.

## Related Plugins

### TDP & Fan Control

- [PowerControl](https://github.com/mengmeet/PowerControl)

I already contributed patches there and it's included in the latest release. It was much faster to extend these fantastic plugin than to integrate the same functionality into DeckyZone itself.

### RGB Control

- [HueSync](https://github.com/honjow/HueSync)

I already contributed patches there and it's hopefully soon released. It was again much faster to extend these fantastic plugin than to integrate the same functionality into DeckyZone itself.

## Installation

Run the following in terminal:

```bash
curl -L https://raw.githubusercontent.com/DeckFilter/DeckyZone/main/install.sh | sh
```

## Feedback

Feedback is really appreciated. Please open an issue if you have feedback, bugs, or feature requests.

If you would like to talk directly, you can also join the Discord server:

- https://discord.gg/dyMMQNKdMH

## Future Ideas

These are ideas, not promised features.

### Display

- Startup movie(s)

### Troubleshooting / Tips & Tricks

- Camera detected status
- System info with EC and display firmware
- Model and board name details
- Battery warning to help prevent BIOS reset

## Credits

Projects currently inspiring DeckyZone:

- [Legion Go Remapper](https://github.com/aarron-lee/LegionGoRemapper)
- [HueSync](https://github.com/honjow/HueSync)
- [PowerControl](https://github.com/mengmeet/PowerControl)
- [DeckyPlumber](https://github.com/aarron-lee/DeckyPlumber)
- [OpenZone](https://github.com/OpenZotacZone/ZotacZone-Drivers)
