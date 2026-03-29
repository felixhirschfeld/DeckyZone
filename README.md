# DeckyZone

[![](https://img.shields.io/github/downloads/DeckFilter/DeckyZone/total.svg)](https://github.com/DeckFilter/DeckyZone/releases)
[![](https://img.shields.io/github/downloads/DeckFilter/DeckyZone/latest/total)](https://github.com/DeckFilter/DeckyZone/releases/latest)
[![](https://img.shields.io/github/v/release/DeckFilter/DeckyZone)](https://github.com/DeckFilter/DeckyZone/releases/latest)

DeckyZone is a Decky plugin for the Zotac Gaming Zone that aims to bridge the most common compatibility gaps until full compatibility lands. I started with controller-related fixes first, because those were the first issues I ran into and I was especially hyped about getting the dials working.

![screenshot](./img/DeckyZone.jpg)

## Current Features

- Enable the Home button
- Enable the dials, including brightness on the right dial
- Adjust rumble / vibration intenstiy
- Fix button prompts and glyphs in games (like Mafia 3, Mafia 1, Avengers)
- Optionally disable trackpads while that fix is active (I tend to touch them with my palm 🤣)

## Installation

Run the following in terminal:

```bash
curl -L https://raw.githubusercontent.com/DeckFilter/DeckyZone/main/install.sh | sh
```

## Compatibility

| Feature                             | SteamOS `main` | Bazzite |
| ----------------------------------- | -------------- | ------- |
| Enable Controller / Dials           | ✅             | ❌      |
| Enable Home Button                  | ✅             | ❌      |
| Enable Brightness Dial              | ✅             | ❌      |
| Adjust rumble / vibration intensity | ✅             | ✅      |
| Test Rumble                         | ✅             | ❌      |
| Button Prompt Fix                   | ✅             | ❌      |
| Disable Trackpads                   | ✅             | ❌      |

Other distros with InputPlumber integrated, such as Nobara and CachyOS, may work too, but are not tested yet. Bazzite will soon switch to InputPlumber.

## Feedback

Feedback is really appreciated. Please open an issue if you have feedback, bugs, or feature requests.

If you would like to talk directly, you can also join the Discord server:

- https://discord.gg/dyMMQNKdMH

## Future Ideas

These are ideas, not promised features.

### Display

- HDR / Washed out colors fix (is working out of the box in latest SteamOS but still not on stable)
- Green tint fix
- Zotac Zone glyphs and images
- Startup movie(s)

### TDP

- Maybe via `"PowerControl"` or built-in
- Per-game profiles
- Per-AC mode behavior
- Separate defaults for SteamUI and games
- Presets and custom profiles

### RGB

- Maybe via `"HueSync"` or built-in

### Fans

- Maybe via a third-party plugin or built-in

### Troubleshooting / Tips & Tricks

- Camera detected status
- System info with EC and display firmware
- Model and board name details
- Battery warning to help prevent BIOS reset

## Credits

Projects currently inspiring DeckyZone:

- `Legion Go Remapper`
- `HueSync`
- `PowerControl`
- `DeckyPlumber`
- `OpenZone`
