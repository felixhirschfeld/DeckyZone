import { DropdownItem, PanelSectionRow } from '@decky/ui'
import { useEffect, useState } from 'react'
import type { TrackpadMode } from '../../types/plugin'

type Props = {
  inputplumberAvailable: boolean
  controllerModeBlocked: boolean
  savingTrackpads: boolean
  trackpadMode: TrackpadMode
  onTrackpadModeChange: (mode: TrackpadMode) => void
}

type TrackpadModeOption = { data: TrackpadMode; label: string }

const INPUTPLUMBER_UNAVAILABLE_DESCRIPTION = 'InputPlumber is not available'
const NO_GAMEPAD_MODE_DESCRIPTION = 'No Gamepad mode detected'
const TRACKPAD_MODE_OPTIONS: TrackpadModeOption[] = [
  { data: 'mouse', label: 'Mouse' },
  { data: 'disabled', label: 'Disabled' },
  { data: 'directional_buttons', label: 'Directional Buttons' },
]

function getTrackpadModeDescription(mode: TrackpadMode) {
  switch (mode) {
    case 'disabled':
      return 'Turns off both trackpads'
    case 'directional_buttons':
      return 'Left pad is D-pad, right pad is A/B/X/Y'
    case 'mouse':
    default:
      return 'Left pad scrolls, right pad moves and clicks'
  }
}

function getTrackpadDescription(inputplumberAvailable: boolean, controllerModeBlocked: boolean, mode: TrackpadMode) {
  if (!inputplumberAvailable) {
    return INPUTPLUMBER_UNAVAILABLE_DESCRIPTION
  }

  if (controllerModeBlocked) {
    return NO_GAMEPAD_MODE_DESCRIPTION
  }

  return getTrackpadModeDescription(mode)
}

const TrackpadPanel = ({
  inputplumberAvailable,
  controllerModeBlocked,
  savingTrackpads,
  trackpadMode,
  onTrackpadModeChange,
}: Props) => {
  const [trackpadOptions] = useState<TrackpadModeOption[]>(() =>
    TRACKPAD_MODE_OPTIONS.map((option) => ({ ...option }))
  )
  const [trackpadModeValue, setTrackpadModeValue] = useState(trackpadMode)
  const [selectedTrackpadOption, setSelectedTrackpadOption] = useState<TrackpadModeOption | undefined>(() =>
    trackpadOptions.find((option) => option.data === trackpadMode)
  )

  useEffect(() => {
    setTrackpadModeValue(trackpadMode)
    setSelectedTrackpadOption(trackpadOptions.find((option) => option.data === trackpadMode))
  }, [trackpadMode, trackpadOptions])

  return (
    <PanelSectionRow>
      <DropdownItem
        key={`trackpad-mode:${trackpadModeValue}`}
        label="Trackpad Mode"
        menuLabel="Trackpad Mode"
        rgOptions={trackpadOptions}
        strDefaultLabel={selectedTrackpadOption?.label ?? 'Mouse'}
        selectedOption={selectedTrackpadOption?.data ?? trackpadModeValue}
        disabled={savingTrackpads || !inputplumberAvailable || controllerModeBlocked}
        description={getTrackpadDescription(inputplumberAvailable, controllerModeBlocked, trackpadModeValue)}
        onChange={(option: { data: TrackpadMode }) => {
          setTrackpadModeValue(option.data)
          setSelectedTrackpadOption(trackpadOptions.find((item) => item.data === option.data))
          onTrackpadModeChange(option.data)
        }}
      />
    </PanelSectionRow>
  )
}

export default TrackpadPanel
