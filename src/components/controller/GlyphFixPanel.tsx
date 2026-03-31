import { PanelSectionRow, ToggleField, gamepadDialogClasses } from '@decky/ui'
import type { ReactNode } from 'react'
import type { ActiveGame } from '../../types/plugin'

type Props = {
  activeGame: ActiveGame | null
  inputplumberAvailable: boolean
  isMissingGlyphFixEnabled: boolean
  isMissingGlyphFixActive: boolean
  isTrackpadsDisabled: boolean
  savingMissingGlyphFix: boolean
  savingMissingGlyphFixTrackpads: boolean
  shouldShowSteamInputDisabledWarning: boolean
  onMissingGlyphFixToggleChange: (enabled: boolean) => void
  onMissingGlyphFixTrackpadsChange: (disabled: boolean) => void
}

const INPUTPLUMBER_UNAVAILABLE_DESCRIPTION = 'InputPlumber is not available.'
const NO_ACTIVE_GAME_GLYPH_FIX_DESCRIPTION = 'Launch a game to enable this fix.'
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

function getMissingGlyphFixDescription(activeGame: ActiveGame | null): ReactNode {
  if (!activeGame) {
    return NO_ACTIVE_GAME_GLYPH_FIX_DESCRIPTION
  }

  const iconSource = getActiveGameIconSource(activeGame)
  const description = `Fixes button prompts and glyphs for ${activeGame.display_name}.`

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

const GlyphFixPanel = ({
  activeGame,
  inputplumberAvailable,
  isMissingGlyphFixEnabled,
  isMissingGlyphFixActive,
  isTrackpadsDisabled,
  savingMissingGlyphFix,
  savingMissingGlyphFixTrackpads,
  shouldShowSteamInputDisabledWarning,
  onMissingGlyphFixToggleChange,
  onMissingGlyphFixTrackpadsChange,
}: Props) => {
  return (
    <>
      <PanelSectionRow>
        <ToggleField
          label="Button Prompt Fix"
          checked={isMissingGlyphFixEnabled}
          onChange={(value: boolean) => onMissingGlyphFixToggleChange(value)}
          disabled={!activeGame || savingMissingGlyphFix || !inputplumberAvailable}
          description={inputplumberAvailable ? getMissingGlyphFixDescription(activeGame) : INPUTPLUMBER_UNAVAILABLE_DESCRIPTION}
        />
      </PanelSectionRow>
      {activeGame && isMissingGlyphFixActive && shouldShowSteamInputDisabledWarning && (
        <PanelSectionRow>
          <div className={gamepadDialogClasses.FieldDescription}>Steam Input disabled</div>
        </PanelSectionRow>
      )}
      {activeGame && isMissingGlyphFixActive && (
        <PanelSectionRow>
          <ToggleField
            label="Disable Trackpads"
            checked={isTrackpadsDisabled}
            onChange={(value: boolean) => onMissingGlyphFixTrackpadsChange(value)}
            disabled={savingMissingGlyphFix || savingMissingGlyphFixTrackpads}
            description={DISABLE_TRACKPADS_DESCRIPTION}
          />
        </PanelSectionRow>
      )}
    </>
  )
}

export default GlyphFixPanel
