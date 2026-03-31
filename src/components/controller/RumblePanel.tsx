import { ButtonItem, PanelSectionRow, SliderField, ToggleField } from '@decky/ui'
import type { PluginSettings } from '../../types/plugin'

type Props = {
  settings: PluginSettings
  savingRumble: boolean
  testingRumble: boolean
  rumbleIntensityDraft: number
  rumbleMessage: string | null
  rumbleMessageKind: 'success' | 'error' | null
  onRumbleToggleChange: (enabled: boolean) => void
  onRumbleIntensityChange: (value: number) => void
  onTestRumble: () => void
}

const DEFAULT_RUMBLE_DESCRIPTION = 'Change and test vibration intensity.'
const RUMBLE_UNAVAILABLE_MESSAGE = 'Rumble device is not available.'

function getRumbleDescription(settings: PluginSettings) {
  if (!settings.rumbleAvailable) {
    return RUMBLE_UNAVAILABLE_MESSAGE
  }

  return DEFAULT_RUMBLE_DESCRIPTION
}

const RumblePanel = ({
  settings,
  savingRumble,
  testingRumble,
  rumbleIntensityDraft,
  rumbleMessage,
  rumbleMessageKind,
  onRumbleToggleChange,
  onRumbleIntensityChange,
  onTestRumble,
}: Props) => {
  return (
    <>
      <PanelSectionRow>
        <ToggleField
          label="Vibration / Rumble"
          checked={settings.rumbleEnabled}
          onChange={(value: boolean) => onRumbleToggleChange(value)}
          disabled={savingRumble}
          description={getRumbleDescription(settings)}
        />
      </PanelSectionRow>
      {settings.rumbleEnabled && (
        <>
          <PanelSectionRow>
            <SliderField
              value={rumbleIntensityDraft}
              min={0}
              max={100}
              step={5}
              notchTicksVisible
              onChange={onRumbleIntensityChange}
              disabled={savingRumble || !settings.rumbleEnabled || !settings.rumbleAvailable}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={() => onTestRumble()}
              disabled={savingRumble || testingRumble || !settings.rumbleEnabled || !settings.rumbleAvailable || !settings.inputplumberAvailable}
            >
              {testingRumble ? 'Testing Rumble...' : `Test  ${rumbleIntensityDraft}% Rumble`}
            </ButtonItem>
          </PanelSectionRow>
          {rumbleMessage && rumbleMessageKind === 'error' && (
            <PanelSectionRow>
              <div
                style={{
                  color: rumbleMessageKind === 'error' ? 'red' : undefined,
                }}
              >
                {rumbleMessage}
              </div>
            </PanelSectionRow>
          )}
        </>
      )}
    </>
  )
}

export default RumblePanel
