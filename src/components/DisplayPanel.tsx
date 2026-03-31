import { callable } from '@decky/api'
import { PanelSection, PanelSectionRow, ToggleField, gamepadDialogClasses } from '@decky/ui'
import { useState } from 'react'
import type { PluginSettings, PluginStatus } from '../types/plugin'

type Props = {
  settings: PluginSettings
  onSettingsChange: (nextSettings: PluginSettings) => void
  onStatusChange: (nextStatus: PluginStatus) => void
}

const setGamescopeZotacProfileEnabled = callable<[boolean], PluginSettings>('set_gamescope_zotac_profile_enabled')
const setGamescopeGreenTintFixEnabled = callable<[boolean], PluginSettings>('set_gamescope_green_tint_fix_enabled')

const RESTART_NOTE = 'Reboot after changing this.'
const NATIVE_COLOR_TEMPERATURE_HINT = 'Tip: Settings -> Display -> Use Native Color Temperature as per preference.'
const MANAGED_FILE_STYLE = {
  fontFamily: 'monospace',
  overflowWrap: 'anywhere' as const,
}

function renderManagedFileDescription(text: string, path: string) {
  return (
    <>
      <div>{text}</div>
      <div>
        Managed file: <span style={MANAGED_FILE_STYLE}>{path}</span>
      </div>
    </>
  )
}

function getZotacProfileDescription(path: string) {
  return renderManagedFileDescription(`Installs the Zotac OLED Gamescope profile on systems that do not ship it yet. ${RESTART_NOTE}`, path)
}

function getGreenTintDescription(settings: PluginSettings, isBaseProfileAvailable: boolean, path: string) {
  if (!isBaseProfileAvailable) {
    return renderManagedFileDescription(`Requires the Zotac OLED profile first. ${RESTART_NOTE}`, path)
  }

  if (settings.gamescopeZotacProfileBuiltIn) {
    return renderManagedFileDescription(`Applies a white point correction to the built-in Zotac OLED profile. ${RESTART_NOTE}`, path)
  }

  return renderManagedFileDescription(`Applies a white point correction to reduce green tint. ${RESTART_NOTE}`, path)
}

function getManagedFileMismatchMessage(label: string, enabled: boolean, path: string) {
  return `${label} did not match the managed file state after the update. Requested ${enabled ? 'on' : 'off'} for ${path}.`
}

function getManagedFileWarning(settings: PluginSettings) {
  if (settings.gamescopeZotacProfileVerificationState === 'error') {
    return (
      <>
        Unable to read or migrate the managed display profile state:{' '}
        <span style={MANAGED_FILE_STYLE}>{settings.gamescopeZotacProfileTargetPath}</span>
      </>
    )
  }

  if (!settings.gamescopeZotacProfileInstalled || settings.gamescopeZotacProfileVerificationState !== 'unexpected') {
    return null
  }

  return (
    <>
      Managed file content does not match the expected DeckyZone profile variant:{' '}
      <span style={MANAGED_FILE_STYLE}>{settings.gamescopeZotacProfileTargetPath}</span>
    </>
  )
}

const DisplayPanel = ({ settings, onSettingsChange, onStatusChange }: Props) => {
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
      if (nextSettings.gamescopeZotacProfileInstalled !== enabled) {
        onStatusChange({
          state: 'failed',
          message: getManagedFileMismatchMessage('Zotac OLED profile', enabled, nextSettings.gamescopeZotacProfileTargetPath),
        })
      }
    } catch (error) {
      onStatusChange({
        state: 'failed',
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
      if (nextSettings.gamescopeGreenTintFixEnabled !== enabled) {
        onStatusChange({
          state: 'failed',
          message: getManagedFileMismatchMessage('Green tint fix', enabled, nextSettings.gamescopeZotacProfileTargetPath),
        })
      }
    } catch (error) {
      onStatusChange({
        state: 'failed',
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
            description={getZotacProfileDescription(settings.gamescopeZotacProfileTargetPath)}
          />
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        <ToggleField
          label="Enable Green Tint Fix"
          checked={settings.gamescopeGreenTintFixEnabled}
          onChange={(value: boolean) => void handleGreenTintFixChange(value)}
          disabled={savingGreenTintFix || !isBaseProfileAvailable}
          description={getGreenTintDescription(settings, isBaseProfileAvailable, settings.gamescopeZotacProfileTargetPath)}
        />
      </PanelSectionRow>
      {getManagedFileWarning(settings) && (
        <PanelSectionRow>
          <div className={gamepadDialogClasses.FieldDescription}>{getManagedFileWarning(settings)}</div>
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        <div className={gamepadDialogClasses.FieldDescription}>{NATIVE_COLOR_TEMPERATURE_HINT}</div>
      </PanelSectionRow>
    </PanelSection>
  )
}

export default DisplayPanel
