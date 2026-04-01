import { PanelSectionRow, ToggleField, gamepadDialogClasses } from '@decky/ui'
import type { ReactNode } from 'react'
import type { ActiveGame } from '../../types/plugin'

type Props = {
  activeGame: ActiveGame | null
  inputplumberAvailable: boolean
  isPerGameSettingsEnabled: boolean
  isButtonPromptFixEnabled: boolean
  isButtonPromptFixActive: boolean
  isTrackpadsDisabled: boolean
  savingPerGameSettings: boolean
  savingButtonPromptFix: boolean
  savingPerGameTrackpads: boolean
  shouldShowSteamInputDisabledWarning: boolean
  onPerGameSettingsToggleChange: (enabled: boolean) => void
  onButtonPromptFixToggleChange: (enabled: boolean) => void
  onPerGameTrackpadsChange: (disabled: boolean) => void
}

const INPUTPLUMBER_UNAVAILABLE_DESCRIPTION = 'InputPlumber is not available.'
const NO_ACTIVE_GAME_PER_GAME_SETTINGS_DESCRIPTION = 'Launch a game to enable per-game settings.'
const BUTTON_PROMPT_FIX_DESCRIPTION = 'Fixes button prompts and glyphs.'
const DISABLE_TRACKPADS_DESCRIPTION = 'Turns off the trackpads while this fix is on.'

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
  isButtonPromptFixActive,
  isTrackpadsDisabled,
  savingPerGameSettings,
  savingButtonPromptFix,
  savingPerGameTrackpads,
  shouldShowSteamInputDisabledWarning,
  onPerGameSettingsToggleChange,
  onButtonPromptFixToggleChange,
  onPerGameTrackpadsChange,
}: Props) => {
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
      {activeGame && isButtonPromptFixActive && shouldShowSteamInputDisabledWarning && (
        <PanelSectionRow>
          <div className={gamepadDialogClasses.FieldDescription}>Steam Input disabled</div>
        </PanelSectionRow>
      )}
      {activeGame && isButtonPromptFixActive && (
        <PanelSectionRow>
          <ToggleField
            label="Disable Trackpads"
            checked={isTrackpadsDisabled}
            onChange={(value: boolean) => onPerGameTrackpadsChange(value)}
            disabled={savingPerGameSettings || savingButtonPromptFix || savingPerGameTrackpads}
            description={DISABLE_TRACKPADS_DESCRIPTION}
          />
        </PanelSectionRow>
      )}
    </>
  )
}

export default PerGameSettingsPanel
