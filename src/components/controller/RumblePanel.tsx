import { ButtonItem, PanelSectionRow, SliderField, ToggleField } from '@decky/ui'

type Props = {
  rumbleEnabled: boolean
  rumbleAvailable: boolean
  savingRumble: boolean
  savingRumbleIntensity: boolean
  testingRumble: boolean
  rumbleIntensityDraft: number
  onRumbleToggleChange: (enabled: boolean) => void
  onRumbleIntensityChange: (value: number) => void
  onTestRumble: () => void
}

const DEFAULT_RUMBLE_DESCRIPTION = 'Change and test vibration intensity'
const RUMBLE_INTENSITY_DESCRIPTION = '75% recommended, 100% is very strong'
const RUMBLE_UNAVAILABLE_MESSAGE = 'Rumble device is not available'

function getRumbleDescription(rumbleAvailable: boolean) {
  if (!rumbleAvailable) {
    return RUMBLE_UNAVAILABLE_MESSAGE
  }

  return DEFAULT_RUMBLE_DESCRIPTION
}

const RumblePanel = ({
  rumbleEnabled,
  rumbleAvailable,
  savingRumble,
  savingRumbleIntensity,
  testingRumble,
  rumbleIntensityDraft,
  onRumbleToggleChange,
  onRumbleIntensityChange,
  onTestRumble,
}: Props) => {
  return (
    <>
      <PanelSectionRow>
        <ToggleField
          label="Rumble Controls"
          checked={rumbleEnabled}
          onChange={(value: boolean) => onRumbleToggleChange(value)}
          disabled={savingRumble}
          description={getRumbleDescription(rumbleAvailable)}
        />
      </PanelSectionRow>
      {rumbleEnabled && (
        <>
          <PanelSectionRow>
            <SliderField
              label="Intensity"
              description={RUMBLE_INTENSITY_DESCRIPTION}
              value={rumbleIntensityDraft}
              min={0}
              max={100}
              step={5}
              notchTicksVisible
              showValue
              resetValue={75}
              onChange={onRumbleIntensityChange}
              disabled={savingRumble || savingRumbleIntensity || !rumbleEnabled || !rumbleAvailable}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={() => onTestRumble()}
              disabled={
                savingRumble ||
                savingRumbleIntensity ||
                testingRumble ||
                !rumbleEnabled ||
                !rumbleAvailable ||
                !inputplumberAvailable
              }
            >
              {testingRumble ? 'Testing Rumble...' : 'Test Rumble'}
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}
    </>
  )
}

export default RumblePanel
