import unittest

from .support import REPO_ROOT


class FrontendStructureTests(unittest.TestCase):
    def test_index_wires_bootstrap_and_top_level_panels(self):
        index_source = REPO_ROOT.joinpath("src", "index.tsx").read_text()

        self.assertIn('import ControllerPanel from "./components/ControllerPanel"', index_source)
        self.assertIn('import DisplayPanel from "./components/DisplayPanel"', index_source)
        self.assertIn('import UpdatesPanel from "./components/UpdatesPanel"', index_source)
        self.assertIn('import ErrorBoundary from "./components/ErrorBoundary"', index_source)
        self.assertIn('from "./types/plugin"', index_source)
        self.assertIn("type BootstrapState =", index_source)
        self.assertIn("Promise.all([getStatus(), getSettings()])", index_source)
        self.assertIn("if (bootstrap.state === 'loading')", index_source)
        self.assertIn("if (bootstrap.state === 'error')", index_source)
        self.assertIn('<ErrorBoundary title="Controller">', index_source)
        self.assertIn('<ErrorBoundary title="Display">', index_source)
        self.assertIn('<ErrorBoundary title="Updates">', index_source)
        self.assertIn("<ControllerPanel", index_source)
        self.assertIn("<DisplayPanel", index_source)
        self.assertIn("<UpdatesPanel", index_source)

    def test_error_boundary_exposes_field_fallback(self):
        boundary_path = REPO_ROOT.joinpath("src", "components", "ErrorBoundary.tsx")
        self.assertTrue(boundary_path.exists())
        boundary_source = boundary_path.read_text()

        self.assertIn("getDerivedStateFromError", boundary_source)
        self.assertIn("componentDidCatch", boundary_source)
        self.assertIn('title?: string', boundary_source)
        self.assertIn("console.log", boundary_source)
        self.assertIn("Field", boundary_source)
        self.assertIn('label="Error"', boundary_source)
        self.assertIn("Error while trying to render", boundary_source)
        self.assertNotIn("PanelSection", boundary_source)
        self.assertNotIn("PanelSectionRow", boundary_source)

    def test_controller_panel_composes_controller_sub_panels_and_keeps_orchestration(self):
        controller_path = REPO_ROOT.joinpath("src", "components", "ControllerPanel.tsx")
        self.assertTrue(controller_path.exists())
        controller_source = controller_path.read_text()

        self.assertIn("../types/plugin", controller_source)
        self.assertIn("./controller/ControllerTogglesPanel", controller_source)
        self.assertIn("./controller/RumblePanel", controller_source)
        self.assertIn("./controller/GlyphFixPanel", controller_source)
        self.assertIn('title="Controller"', controller_source)
        self.assertIn('set_home_button_enabled', controller_source)
        self.assertIn('set_brightness_dial_fix_enabled', controller_source)
        self.assertIn('set_missing_glyph_fix_enabled', controller_source)
        self.assertIn('test_rumble', controller_source)
        self.assertIn("<ControllerTogglesPanel", controller_source)
        self.assertIn("<RumblePanel", controller_source)
        self.assertIn("<GlyphFixPanel", controller_source)

    def test_controller_toggles_panel_keeps_controller_copy(self):
        toggles_path = REPO_ROOT.joinpath("src", "components", "controller", "ControllerTogglesPanel.tsx")
        self.assertTrue(toggles_path.exists())
        toggles_source = toggles_path.read_text()

        self.assertIn('Enable Controller', toggles_source)
        self.assertIn('Enable Home Button', toggles_source)
        self.assertIn('Enable Brightness Dial', toggles_source)
        self.assertIn('InputPlumber is not available.', toggles_source)

    def test_rumble_panel_keeps_rumble_controls_and_copy(self):
        rumble_path = REPO_ROOT.joinpath("src", "components", "controller", "RumblePanel.tsx")
        self.assertTrue(rumble_path.exists())
        rumble_source = rumble_path.read_text()

        self.assertIn('Vibration / Rumble', rumble_source)
        self.assertIn('Testing Rumble...', rumble_source)
        self.assertIn('Test  ${rumbleIntensityDraft}% Rumble', rumble_source)

    def test_glyph_fix_panel_keeps_glyph_fix_copy(self):
        glyph_fix_path = REPO_ROOT.joinpath("src", "components", "controller", "GlyphFixPanel.tsx")
        self.assertTrue(glyph_fix_path.exists())
        glyph_fix_source = glyph_fix_path.read_text()

        self.assertIn('Button Prompt Fix', glyph_fix_source)
        self.assertIn('Launch a game to enable this fix.', glyph_fix_source)
        self.assertIn('Disable Trackpads', glyph_fix_source)
        self.assertIn('Turns off the trackpads while this fix is on.', glyph_fix_source)
        self.assertIn('Steam Input disabled', glyph_fix_source)

    def test_updates_panel_keeps_update_actions_and_status_copy(self):
        updates_path = REPO_ROOT.joinpath("src", "components", "UpdatesPanel.tsx")
        self.assertTrue(updates_path.exists())
        updates_source = updates_path.read_text()

        self.assertIn('title="Updates"', updates_source)
        self.assertIn("getLatestVersionNum", updates_source)
        self.assertIn("otaUpdate", updates_source)
        self.assertIn("Installed Version", updates_source)
        self.assertIn("Latest Version", updates_source)
        self.assertIn("Update to", updates_source)
        self.assertIn("Reinstall Plugin", updates_source)
        self.assertIn("Retry", updates_source)
        self.assertIn("Failed to fetch the latest version.", updates_source)
        self.assertIn("Failed to update DeckyZone.", updates_source)

    def test_display_panel_keeps_gamescope_wiring_and_warning_copy(self):
        display_path = REPO_ROOT.joinpath("src", "components", "DisplayPanel.tsx")
        plugin_types_path = REPO_ROOT.joinpath("src", "types", "plugin.ts")
        legacy_plugin_types_path = REPO_ROOT.joinpath("src", "pluginTypes.ts")
        helper_path = REPO_ROOT.joinpath("py_modules", "gamescope_display_profiles.py")

        self.assertTrue(display_path.exists())
        self.assertTrue(plugin_types_path.exists())
        self.assertFalse(legacy_plugin_types_path.exists())
        self.assertTrue(helper_path.exists())

        display_source = display_path.read_text()
        plugin_types_source = plugin_types_path.read_text()
        helper_source = helper_path.read_text()

        self.assertIn("../types/plugin", display_source)
        self.assertIn('title="Display"', display_source)
        self.assertIn('Enable Zotac OLED Profile', display_source)
        self.assertIn('Enable Green Tint Fix', display_source)
        self.assertIn('gamescopeZotacProfileTargetPath', display_source)
        self.assertIn('gamescopeZotacProfileVerificationState', display_source)
        self.assertIn('set_gamescope_zotac_profile_enabled', display_source)
        self.assertIn('set_gamescope_green_tint_fix_enabled', display_source)
        self.assertIn('Managed file:', display_source)
        self.assertIn('Unable to read or migrate the managed display profile state:', display_source)
        self.assertIn('Settings -> Display -> Use Native Color Temperature', display_source)
        self.assertIn('gamescopeZotacProfileTargetPath', plugin_types_source)
        self.assertIn('gamescopeZotacProfileVerificationState', plugin_types_source)
        self.assertIn('class GamescopeDisplayProfiles', helper_source)
        self.assertIn('zotac.zone.oled.lua', helper_source)
        self.assertTrue(REPO_ROOT.joinpath("assets", "gamescope", "zotac.zone.oled.lua").exists())
        self.assertTrue(REPO_ROOT.joinpath("assets", "gamescope", "zotac.zone.green-tint.lua").exists())
