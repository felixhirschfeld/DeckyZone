import { PanelSectionRow, ToggleField } from '@decky/ui'
import type { PluginSettings } from '../../types/plugin'

type Props = {
  settings: PluginSettings
  savingStartup: boolean
  savingHomeButton: boolean
  savingBrightnessDialFix: boolean
  onStartupToggleChange: (enabled: boolean) => void
  onHomeButtonToggleChange: (enabled: boolean) => void
  onBrightnessDialFixToggleChange: (enabled: boolean) => void
}

const CONTROLLER_FEATURES_DESCRIPTION = 'Turns on controller features.'
const HOME_BUTTON_TOGGLE_DESCRIPTION = 'Opens Home.'
const BRIGHTNESS_DIAL_FIX_DESCRIPTION = 'Uses the right dial for screen brightness.'
const INPUTPLUMBER_UNAVAILABLE_DESCRIPTION = 'InputPlumber is not available.'

function getStartupDescription(settings: PluginSettings) {
  if (!settings.inputplumberAvailable) {
    return INPUTPLUMBER_UNAVAILABLE_DESCRIPTION
  }

  return CONTROLLER_FEATURES_DESCRIPTION
}

const ControllerTogglesPanel = ({
  settings,
  savingStartup,
  savingHomeButton,
  savingBrightnessDialFix,
  onStartupToggleChange,
  onHomeButtonToggleChange,
  onBrightnessDialFixToggleChange,
}: Props) => {
  return (
    <>
      <PanelSectionRow>
        <ToggleField
          label="Enable Controller Features"
          checked={settings.startupApplyEnabled}
          onChange={(value: boolean) => onStartupToggleChange(value)}
          disabled={savingStartup || !settings.inputplumberAvailable}
          description={getStartupDescription(settings)}
        />
      </PanelSectionRow>
      {settings.startupApplyEnabled && (
        <>
          <PanelSectionRow>
            <ToggleField
              label="Enable Home Button"
              checked={settings.homeButtonEnabled}
              onChange={(value: boolean) => onHomeButtonToggleChange(value)}
              disabled={savingHomeButton || !settings.inputplumberAvailable}
              description={settings.inputplumberAvailable ? HOME_BUTTON_TOGGLE_DESCRIPTION : INPUTPLUMBER_UNAVAILABLE_DESCRIPTION}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ToggleField
              label="Enable Brightness Dial"
              checked={settings.brightnessDialFixEnabled}
              onChange={(value: boolean) => onBrightnessDialFixToggleChange(value)}
              disabled={savingBrightnessDialFix || !settings.inputplumberAvailable}
              description={settings.inputplumberAvailable ? BRIGHTNESS_DIAL_FIX_DESCRIPTION : INPUTPLUMBER_UNAVAILABLE_DESCRIPTION}
            />
          </PanelSectionRow>
        </>
      )}
    </>
  )
}

export default ControllerTogglesPanel
