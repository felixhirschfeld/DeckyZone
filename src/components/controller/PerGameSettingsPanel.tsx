import { PanelSectionRow, ToggleField } from '@decky/ui'
import type { ReactNode } from 'react'
import type { ActiveGame } from '../../types/plugin'

type Props = {
  activeGame: ActiveGame | null
  inputplumberAvailable: boolean
  isPerGameSettingsEnabled: boolean
  isButtonPromptFixEnabled: boolean
  savingPerGameSettings: boolean
  savingButtonPromptFix: boolean
  onPerGameSettingsToggleChange: (enabled: boolean) => void
  onButtonPromptFixToggleChange: (enabled: boolean) => void
}

const INPUTPLUMBER_UNAVAILABLE_DESCRIPTION = 'InputPlumber is not available'
const NO_ACTIVE_GAME_PER_GAME_SETTINGS_DESCRIPTION = 'Launch a game to enable per-game settings'
const BUTTON_PROMPT_FIX_DESCRIPTION = 'Fixes button prompts and glyphs'
// TODO: Re-enable these remap options after M1/M2 remap behavior is fully confirmed on-device.
// const M1_REMAP_DESCRIPTION = 'Maps M1 while this fix is on'
// const M2_REMAP_DESCRIPTION = 'Maps M2 while this fix is on'
// const PER_GAME_REMAP_OPTIONS = [
//   { data: 'none', label: 'None' },
//   { data: 'a', label: 'A' },
//   { data: 'b', label: 'B' },
//   { data: 'x', label: 'X' },
//   { data: 'y', label: 'Y' },
//   { data: 'select', label: 'View / Select' },
//   { data: 'start', label: 'Menu / Start' },
//   { data: 'lb', label: 'LB' },
//   { data: 'rb', label: 'RB' },
//   { data: 'lt', label: 'LT' },
//   { data: 'rt', label: 'RT' },
//   { data: 'ls', label: 'LS' },
//   { data: 'rs', label: 'RS' },
//   { data: 'dpad_up', label: 'D-Pad Up' },
//   { data: 'dpad_down', label: 'D-Pad Down' },
//   { data: 'dpad_left', label: 'D-Pad Left' },
//   { data: 'dpad_right', label: 'D-Pad Right' },
// ] as const

function getActiveGameIconSource(activeGame: ActiveGame | null) {
  if (!activeGame) {
    return null
  }

  if (activeGame.icon_data && activeGame.icon_data_format) {
    return `data:image/${activeGame.icon_data_format};base64,${activeGame.icon_data}`
  }

  if (activeGame.icon_hash) {
    return `/assets/${activeGame.appid}/${activeGame.icon_hash}.jpg?c=${activeGame.local_cache_version ?? ''}`
  }

  return null
}

function renderActiveGameDescription(activeGame: ActiveGame | null, description: string): ReactNode {
  if (!activeGame) {
    return description
  }

  const iconSource = getActiveGameIconSource(activeGame)

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      {iconSource ? <img src={iconSource} width={20} height={20} style={{ borderRadius: '4px', flexShrink: 0 }} /> : null}
      <div
        style={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {description}
      </div>
    </div>
  )
}

function getPerGameSettingsDescription(activeGame: ActiveGame | null): ReactNode {
  if (!activeGame) {
    return NO_ACTIVE_GAME_PER_GAME_SETTINGS_DESCRIPTION
  }

  return renderActiveGameDescription(activeGame, activeGame.display_name)
}

const PerGameSettingsPanel = ({
  activeGame,
  inputplumberAvailable,
  isPerGameSettingsEnabled,
  isButtonPromptFixEnabled,
  savingPerGameSettings,
  savingButtonPromptFix,
  onPerGameSettingsToggleChange,
  onButtonPromptFixToggleChange,
}: Props) => {
  // TODO: Re-enable these locals after M1/M2 remap behavior is fully confirmed on-device.
  // const remapDropdownDisabled =
  //   savingPerGameSettings || savingButtonPromptFix || savingPerGameTrackpads || savingPerGameRemaps || !inputplumberAvailable
  // const m1RemapDropdownProps = {
  //   label: 'M1 Remap',
  //   menuLabel: 'M1 Remap',
  //   rgOptions: PER_GAME_REMAP_OPTIONS,
  //   selectedOption: m1RemapTarget,
  //   strDefaultLabel: 'None',
  //   description: M1_REMAP_DESCRIPTION,
  //   disabled: remapDropdownDisabled,
  //   onChange: (option: { data: PerGameRemapTarget }) => onPerGameM1RemapTargetChange(option.data),
  // } as any
  // const m2RemapDropdownProps = {
  //   label: 'M2 Remap',
  //   menuLabel: 'M2 Remap',
  //   rgOptions: PER_GAME_REMAP_OPTIONS,
  //   selectedOption: m2RemapTarget,
  //   strDefaultLabel: 'None',
  //   description: M2_REMAP_DESCRIPTION,
  //   disabled: remapDropdownDisabled,
  //   onChange: (option: { data: PerGameRemapTarget }) => onPerGameM2RemapTargetChange(option.data),
  // } as any

  return (
    <>
      <PanelSectionRow>
        <ToggleField
          label="Enable Per-Game Settings"
          checked={isPerGameSettingsEnabled}
          onChange={(value: boolean) => onPerGameSettingsToggleChange(value)}
          disabled={!activeGame || savingPerGameSettings || !inputplumberAvailable}
          description={inputplumberAvailable ? getPerGameSettingsDescription(activeGame) : INPUTPLUMBER_UNAVAILABLE_DESCRIPTION}
        />
      </PanelSectionRow>
      {activeGame && isPerGameSettingsEnabled && (
        <PanelSectionRow>
          <ToggleField
            label="Button Prompt Fix"
            checked={isButtonPromptFixEnabled}
            onChange={(value: boolean) => onButtonPromptFixToggleChange(value)}
            disabled={savingPerGameSettings || savingButtonPromptFix || !inputplumberAvailable}
            description={inputplumberAvailable ? BUTTON_PROMPT_FIX_DESCRIPTION : INPUTPLUMBER_UNAVAILABLE_DESCRIPTION}
          />
        </PanelSectionRow>
      )}
    </>
  )
}

export default PerGameSettingsPanel
