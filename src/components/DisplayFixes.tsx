import { callable } from "@decky/api"
import { PanelSection, PanelSectionRow, ToggleField, gamepadDialogClasses } from "@decky/ui"
import { useState } from "react"
import type { PluginSettings, PluginStatus } from "../pluginTypes"

type Props = {
  settings: PluginSettings
  onSettingsChange: (nextSettings: PluginSettings) => void
  onStatusChange: (nextStatus: PluginStatus) => void
}

const setGamescopeZotacProfileEnabled = callable<[boolean], PluginSettings>("set_gamescope_zotac_profile_enabled")
const setGamescopeGreenTintFixEnabled = callable<[boolean], PluginSettings>("set_gamescope_green_tint_fix_enabled")

const RESTART_NOTE = "Restart Gamescope or reboot after changing this."
const NATIVE_COLOR_TEMPERATURE_HINT =
  "Tip: Settings -> Display -> Use Native Color Temperature can also improve colors. You can try combining it with this fix."

function getZotacProfileDescription() {
  return `Installs the Zotac OLED Gamescope profile on systems that do not ship it yet. ${RESTART_NOTE}`
}

function getGreenTintDescription(settings: PluginSettings, isBaseProfileAvailable: boolean) {
  if (!isBaseProfileAvailable) {
    return `Requires the Zotac OLED profile first. ${RESTART_NOTE}`
  }

  if (settings.gamescopeZotacProfileBuiltIn) {
    return `Applies a white point correction to the built-in Zotac OLED profile. ${RESTART_NOTE}`
  }

  return `Applies a white point correction to reduce green tint. ${RESTART_NOTE}`
}

const DisplayFixes = ({ settings, onSettingsChange, onStatusChange }: Props) => {
  // TODO: If rapid toggling ever causes stale UI state, serialize these requests
  // or ignore out-of-order responses instead of relying only on disabled toggles
  // and backend file-state readback.
  const [savingZotacProfile, setSavingZotacProfile] = useState(false)
  const [savingGreenTintFix, setSavingGreenTintFix] = useState(false)
  const isBaseProfileAvailable = settings.gamescopeZotacProfileBuiltIn || settings.gamescopeZotacProfileInstalled

  const handleZotacProfileChange = async (enabled: boolean) => {
    setSavingZotacProfile(true)
    try {
      const nextSettings = await setGamescopeZotacProfileEnabled(enabled)
      onSettingsChange(nextSettings)
    } catch (error) {
      onStatusChange({
        state: "failed",
        message: `Failed to update Zotac OLED profile: ${String(error)}`,
      })
    } finally {
      setSavingZotacProfile(false)
    }
  }

  const handleGreenTintFixChange = async (enabled: boolean) => {
    setSavingGreenTintFix(true)
    try {
      const nextSettings = await setGamescopeGreenTintFixEnabled(enabled)
      onSettingsChange(nextSettings)
    } catch (error) {
      onStatusChange({
        state: "failed",
        message: `Failed to update green tint fix: ${String(error)}`,
      })
    } finally {
      setSavingGreenTintFix(false)
    }
  }

  return (
    <PanelSection title="Display">
      {!settings.gamescopeZotacProfileBuiltIn && (
        <PanelSectionRow>
          <ToggleField
            label="Enable Zotac OLED Profile"
            checked={settings.gamescopeZotacProfileInstalled}
            onChange={(value: boolean) => void handleZotacProfileChange(value)}
            disabled={savingZotacProfile}
            description={getZotacProfileDescription()}
          />
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        <ToggleField
          label="Enable Green Tint Fix"
          checked={settings.gamescopeGreenTintFixEnabled}
          onChange={(value: boolean) => void handleGreenTintFixChange(value)}
          disabled={savingGreenTintFix || !isBaseProfileAvailable}
          description={getGreenTintDescription(settings, isBaseProfileAvailable)}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <div className={gamepadDialogClasses.FieldDescription}>{NATIVE_COLOR_TEMPERATURE_HINT}</div>
      </PanelSectionRow>
    </PanelSection>
  )
}

export default DisplayFixes
