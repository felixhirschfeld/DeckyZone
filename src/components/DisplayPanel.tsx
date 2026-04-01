import { callable } from '@decky/api'
import { PanelSection, PanelSectionRow, ToggleField, gamepadDialogClasses } from '@decky/ui'
import { useState } from 'react'
import type { PluginSettings } from '../types/plugin'

type Props = {
  settings: PluginSettings
  onSettingsChange: (nextSettings: PluginSettings) => void
}

const setGamescopeZotacProfileEnabled = callable<[boolean], PluginSettings>('set_gamescope_zotac_profile_enabled')
const setGamescopeGreenTintFixEnabled = callable<[boolean], PluginSettings>('set_gamescope_green_tint_fix_enabled')

const RESTART_NOTE = 'Reboot after changing this.'
const NATIVE_COLOR_TEMPERATURE_HINT = 'Tip: Settings -> Display -> Use Native Color Temperature as per preference.'
const SUPPORT_POPUP_HINT = 'Open the header info popup for details.'
const DISPLAY_UPDATE_FAILED_NOTICE = `Couldn't update the display setting. ${SUPPORT_POPUP_HINT}`
const DISPLAY_MISMATCH_NOTICE = `Display profile did not match the requested state. ${SUPPORT_POPUP_HINT}`
const DISPLAY_VERIFICATION_NOTICE = `Display profile needs attention. ${SUPPORT_POPUP_HINT}`
const ZOTAC_PROFILE_DESCRIPTION = `Installs the Zotac OLED Gamescope profile on systems that do not ship it yet. ${RESTART_NOTE}`

function getGreenTintDescription(settings: PluginSettings, isBaseProfileAvailable: boolean) {
  if (!isBaseProfileAvailable) {
    return `Requires the Zotac OLED profile first. ${RESTART_NOTE}`
  }

  if (settings.gamescopeZotacProfileBuiltIn) {
    return `Applies a white point correction to the built-in Zotac OLED profile. ${RESTART_NOTE}`
  }

  return `Applies a white point correction to reduce green tint. ${RESTART_NOTE}`
}

function getDisplayVerificationNotice(settings: PluginSettings) {
  if (
    settings.gamescopeZotacProfileVerificationState === 'error' ||
    settings.gamescopeZotacProfileVerificationState === 'unexpected'
  ) {
    return DISPLAY_VERIFICATION_NOTICE
  }

  return null
}

const DisplayPanel = ({ settings, onSettingsChange }: Props) => {
  // TODO: If rapid toggling ever causes stale UI state, serialize these requests
  // or ignore out-of-order responses instead of relying only on disabled toggles
  // and backend file-state readback.
  const [savingZotacProfile, setSavingZotacProfile] = useState(false)
  const [savingGreenTintFix, setSavingGreenTintFix] = useState(false)
  const [displayNotice, setDisplayNotice] = useState<string | null>(null)
  const isBaseProfileAvailable = settings.gamescopeZotacProfileBuiltIn || settings.gamescopeZotacProfileInstalled
  const visibleDisplayNotice = displayNotice ?? getDisplayVerificationNotice(settings)

  const handleZotacProfileChange = async (enabled: boolean) => {
    setSavingZotacProfile(true)
    try {
      const nextSettings = await setGamescopeZotacProfileEnabled(enabled)
      onSettingsChange(nextSettings)
      setDisplayNotice(nextSettings.gamescopeZotacProfileInstalled !== enabled ? DISPLAY_MISMATCH_NOTICE : null)
    } catch {
      setDisplayNotice(DISPLAY_UPDATE_FAILED_NOTICE)
    } finally {
      setSavingZotacProfile(false)
    }
  }

  const handleGreenTintFixChange = async (enabled: boolean) => {
    setSavingGreenTintFix(true)
    try {
      const nextSettings = await setGamescopeGreenTintFixEnabled(enabled)
      onSettingsChange(nextSettings)
      setDisplayNotice(nextSettings.gamescopeGreenTintFixEnabled !== enabled ? DISPLAY_MISMATCH_NOTICE : null)
    } catch {
      setDisplayNotice(DISPLAY_UPDATE_FAILED_NOTICE)
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
            description={ZOTAC_PROFILE_DESCRIPTION}
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
      {visibleDisplayNotice && (
        <PanelSectionRow>
          <div className={gamepadDialogClasses.FieldDescription}>{visibleDisplayNotice}</div>
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        <div className={gamepadDialogClasses.FieldDescription}>{NATIVE_COLOR_TEMPERATURE_HINT}</div>
      </PanelSectionRow>
    </PanelSection>
  )
}

export default DisplayPanel
