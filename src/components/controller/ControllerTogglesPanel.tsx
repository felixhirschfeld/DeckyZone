import { PanelSectionRow, ToggleField } from '@decky/ui'
import type { PluginSettings, PluginStatus } from '../../pluginTypes'

type Props = {
  status: PluginStatus
  settings: PluginSettings
  savingStartup: boolean
  savingHomeButton: boolean
  savingBrightnessDialFix: boolean
  onStartupToggleChange: (enabled: boolean) => void
  onHomeButtonToggleChange: (enabled: boolean) => void
  onBrightnessDialFixToggleChange: (enabled: boolean) => void
}

const DEFAULT_STARTUP_DESCRIPTION = 'Sets the Zotac controller now and after boot. Makes the dials work.'
const HOME_BUTTON_TOGGLE_DESCRIPTION = 'Opens Home.'
const HOME_BUTTON_TOGGLE_DISABLED_DESCRIPTION = 'Opens Home. Enable Controller first.'
const DEFAULT_BRIGHTNESS_DIAL_FIX_DESCRIPTION = 'Uses the right dial for screen brightness.'
const BRIGHTNESS_DIAL_FIX_DISABLED_DESCRIPTION = 'Uses the right dial for screen brightness. Enable Controller first.'
const INPUTPLUMBER_UNAVAILABLE_DESCRIPTION = 'InputPlumber is not available.'

function getStartupDescription(status: PluginStatus, settings: PluginSettings) {
  if (!settings.inputplumberAvailable) {
    return INPUTPLUMBER_UNAVAILABLE_DESCRIPTION
  }

  if (status.state === 'failed' || status.state === 'disabled' || status.state === 'unsupported') {
    return status.message
  }

  return DEFAULT_STARTUP_DESCRIPTION
}

function getBrightnessDialFixDescription(settings: PluginSettings) {
  if (!settings.inputplumberAvailable) {
    return INPUTPLUMBER_UNAVAILABLE_DESCRIPTION
  }

  if (!settings.startupApplyEnabled) {
    return BRIGHTNESS_DIAL_FIX_DISABLED_DESCRIPTION
  }

  return DEFAULT_BRIGHTNESS_DIAL_FIX_DESCRIPTION
}

const ControllerTogglesPanel = ({
  status,
  settings,
  savingStartup,
  savingHomeButton,
  savingBrightnessDialFix,
  onStartupToggleChange,
  onHomeButtonToggleChange,
  onBrightnessDialFixToggleChange,
}: Props) => {
  const controllerDependentToggleDisabled = !settings.startupApplyEnabled
  const inputplumberDependentControlDisabled = !settings.inputplumberAvailable

  return (
    <>
      <PanelSectionRow>
        <ToggleField
          label="Enable Controller"
          checked={settings.startupApplyEnabled}
          onChange={(value: boolean) => onStartupToggleChange(value)}
          disabled={savingStartup || !settings.inputplumberAvailable}
          description={getStartupDescription(status, settings)}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label="Enable Home Button"
          checked={settings.homeButtonEnabled}
          onChange={(value: boolean) => onHomeButtonToggleChange(value)}
          disabled={savingHomeButton || !settings.startupApplyEnabled || !settings.inputplumberAvailable}
          description={
            inputplumberDependentControlDisabled
              ? INPUTPLUMBER_UNAVAILABLE_DESCRIPTION
              : controllerDependentToggleDisabled
                ? HOME_BUTTON_TOGGLE_DISABLED_DESCRIPTION
                : HOME_BUTTON_TOGGLE_DESCRIPTION
          }
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label="Enable Brightness Dial"
          checked={settings.brightnessDialFixEnabled}
          onChange={(value: boolean) => onBrightnessDialFixToggleChange(value)}
          disabled={savingBrightnessDialFix || !settings.startupApplyEnabled || !settings.inputplumberAvailable}
          description={getBrightnessDialFixDescription(settings)}
        />
      </PanelSectionRow>
    </>
  )
}

export default ControllerTogglesPanel
