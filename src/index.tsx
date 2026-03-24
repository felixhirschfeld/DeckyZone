import { ButtonItem, PanelSection, PanelSectionRow, Router, SliderField, staticClasses, ToggleField } from '@decky/ui'
import { callable, definePlugin } from '@decky/api'
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { FaSlidersH } from 'react-icons/fa'

type PluginStatus = {
  state: string
  message: string
}

type MissingGlyphFixGameSettings = {
  disableTrackpads: boolean
}

type PluginSettings = {
  startupApplyEnabled: boolean
  inputplumberAvailable: boolean
  rumbleEnabled: boolean
  rumbleIntensity: number
  rumbleAvailable: boolean
  missingGlyphFixGames: Record<string, MissingGlyphFixGameSettings>
}

type ActiveGame = {
  appid: string
  display_name: string
  icon_data?: string
  icon_data_format?: string
  icon_hash?: string
  local_cache_version?: number | string
}

const getStatus = callable<[], PluginStatus>('get_status')
const getSettings = callable<[], PluginSettings>('get_settings')
const setStartupApplyEnabled = callable<[boolean], PluginSettings>('set_startup_apply_enabled')
const setMissingGlyphFixEnabled = callable<[string, boolean], PluginSettings>('set_missing_glyph_fix_enabled')
const setMissingGlyphFixTrackpadsDisabled = callable<[string, boolean], PluginSettings>('set_missing_glyph_fix_trackpads_disabled')
const syncMissingGlyphFixTarget = callable<[string], boolean>('sync_missing_glyph_fix_target')
const setRumbleEnabled = callable<[boolean], PluginSettings>('set_rumble_enabled')
const setRumbleIntensity = callable<[number], PluginSettings>('set_rumble_intensity')
const testRumble = callable<[], boolean>('test_rumble')

const DEFAULT_APP_ID = '0'
const ACTIVE_GAME_POLL_INTERVAL_MS = 1000
const DEFAULT_STARTUP_DESCRIPTION = 'Restores the Zotac controller after boot.'
const DEFAULT_RUMBLE_DESCRIPTION = 'Change and test vibration intensity.'
const RUMBLE_UNAVAILABLE_MESSAGE = 'Rumble device is not available.'
const NO_ACTIVE_GAME_GLYPH_FIX_DESCRIPTION = 'Launch a game to enable this glyph fix.'
const DISABLE_TRACKPADS_DESCRIPTION = 'Turns off the trackpads while this glyph fix is active for the current game.'

function getStartupDescription(status: PluginStatus, settings: PluginSettings) {
  if (!settings.inputplumberAvailable) {
    return 'InputPlumber is not available.'
  }

  if (status.state === 'failed' || status.state === 'disabled' || status.state === 'unsupported') {
    return status.message
  }

  return DEFAULT_STARTUP_DESCRIPTION
}

function getRumbleDescription(settings: PluginSettings) {
  if (!settings.rumbleAvailable) {
    return RUMBLE_UNAVAILABLE_MESSAGE
  }

  return DEFAULT_RUMBLE_DESCRIPTION
}

function getActiveGame(): ActiveGame | null {
  const activeApp = Router.MainRunningApp as Partial<ActiveGame> | undefined
  const appId = `${activeApp?.appid ?? DEFAULT_APP_ID}`

  if (appId === DEFAULT_APP_ID) {
    return null
  }

  return {
    appid: appId,
    display_name: activeApp?.display_name || 'Current Game',
    icon_data: activeApp?.icon_data,
    icon_data_format: activeApp?.icon_data_format,
    icon_hash: activeApp?.icon_hash,
    local_cache_version: activeApp?.local_cache_version,
  }
}

function areGamesEqual(left: ActiveGame | null, right: ActiveGame | null) {
  if (!left && !right) {
    return true
  }

  if (!left || !right) {
    return false
  }

  return (
    left.appid === right.appid &&
    left.display_name === right.display_name &&
    left.icon_data === right.icon_data &&
    left.icon_data_format === right.icon_data_format &&
    left.icon_hash === right.icon_hash &&
    left.local_cache_version === right.local_cache_version
  )
}

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
        {`For ${activeGame.display_name}.`}
      </div>
    </div>
  )
}

function Content() {
  const [status, setStatus] = useState<PluginStatus>({
    state: 'loading',
    message: 'Loading DeckyZone status.',
  })
  const [settings, setSettings] = useState<PluginSettings>({
    startupApplyEnabled: true,
    inputplumberAvailable: true,
    rumbleEnabled: true,
    rumbleIntensity: 75,
    rumbleAvailable: true,
    missingGlyphFixGames: {},
  })
  const [activeGame, setActiveGame] = useState<ActiveGame | null>(null)
  const [rumbleIntensityDraft, setRumbleIntensityDraft] = useState(75)
  const [savingStartup, setSavingStartup] = useState(false)
  const [savingMissingGlyphFix, setSavingMissingGlyphFix] = useState(false)
  const [savingMissingGlyphFixTrackpads, setSavingMissingGlyphFixTrackpads] = useState(false)
  const [savingRumble, setSavingRumble] = useState(false)
  const [testingRumble, setTestingRumble] = useState(false)
  const [rumbleMessage, setRumbleMessage] = useState<string | null>(null)
  const [rumbleMessageKind, setRumbleMessageKind] = useState<'success' | 'error' | null>(null)
  const rumbleIntensityLatestValue = useRef(75)
  const rumbleIntensitySaveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastActiveGameId = useRef<string | null>(null)

  const activeGameGlyphFixSettings = activeGame ? settings.missingGlyphFixGames[activeGame.appid] : undefined
  const isMissingGlyphFixEnabled = Boolean(activeGameGlyphFixSettings)
  const isTrackpadsDisabled = activeGameGlyphFixSettings?.disableTrackpads ?? true

  const clearPendingRumbleIntensitySave = () => {
    if (rumbleIntensitySaveTimeout.current !== null) {
      clearTimeout(rumbleIntensitySaveTimeout.current)
      rumbleIntensitySaveTimeout.current = null
    }
  }

  const syncActiveGameTarget = async (appId: string) => {
    try {
      await syncMissingGlyphFixTarget(appId)
    } catch (error) {
      console.error('Failed to sync missing glyph fix target', error)
    }
  }

  const loadStatus = async () => {
    const nextStatus = await getStatus()
    setStatus(nextStatus)
  }

  const loadAll = async () => {
    try {
      const [nextStatus, nextSettings] = await Promise.all([getStatus(), getSettings()])
      setStatus(nextStatus)
      setSettings(nextSettings)
      setRumbleIntensityDraft(nextSettings.rumbleIntensity)
      rumbleIntensityLatestValue.current = nextSettings.rumbleIntensity
      if (!nextSettings.rumbleAvailable) {
        setRumbleMessage(null)
        setRumbleMessageKind(null)
      }
    } catch (error) {
      setStatus({
        state: 'failed',
        message: `Failed to load plugin state: ${String(error)}`,
      })
    }
  }

  const handleStartupToggleChange = async (enabled: boolean) => {
    setSavingStartup(true)
    try {
      const nextSettings = await setStartupApplyEnabled(enabled)
      setSettings(nextSettings)
      await loadStatus()
      await syncActiveGameTarget(activeGame?.appid ?? DEFAULT_APP_ID)
    } catch (error) {
      setStatus({
        state: 'failed',
        message: `Failed to update startup setting: ${String(error)}`,
      })
    } finally {
      setSavingStartup(false)
    }
  }

  const handleMissingGlyphFixToggleChange = async (enabled: boolean) => {
    if (!activeGame) {
      return
    }

    setSavingMissingGlyphFix(true)
    try {
      const nextSettings = await setMissingGlyphFixEnabled(activeGame.appid, enabled)
      setSettings(nextSettings)
      await syncActiveGameTarget(activeGame.appid)
    } catch (error) {
      setStatus({
        state: 'failed',
        message: `Failed to update missing glyph fix: ${String(error)}`,
      })
    } finally {
      setSavingMissingGlyphFix(false)
    }
  }

  const handleRumbleToggleChange = async (enabled: boolean) => {
    if (!enabled) {
      clearPendingRumbleIntensitySave()
    }

    setSavingRumble(true)
    try {
      const nextSettings = await setRumbleEnabled(enabled)
      setSettings(nextSettings)
      setRumbleIntensityDraft(nextSettings.rumbleIntensity)
      rumbleIntensityLatestValue.current = nextSettings.rumbleIntensity
      setRumbleMessage(null)
      setRumbleMessageKind(null)
      await loadStatus()
    } catch (error) {
      setStatus({
        state: 'failed',
        message: `Failed to update rumble setting: ${String(error)}`,
      })
    } finally {
      setSavingRumble(false)
    }
  }

  const saveRumbleIntensity = async (value: number) => {
    try {
      const nextSettings = await setRumbleIntensity(value)
      setSettings((currentSettings) => ({
        ...currentSettings,
        rumbleIntensity: nextSettings.rumbleIntensity,
        rumbleAvailable: nextSettings.rumbleAvailable,
      }))
      setRumbleMessage(null)
      setRumbleMessageKind(null)
    } catch (error) {
      setStatus({
        state: 'failed',
        message: `Failed to update vibration intensity: ${String(error)}`,
      })
    }
  }

  const handleRumbleIntensityChange = (value: number) => {
    setRumbleIntensityDraft(value)
    rumbleIntensityLatestValue.current = value
    clearPendingRumbleIntensitySave()
    rumbleIntensitySaveTimeout.current = setTimeout(() => {
      rumbleIntensitySaveTimeout.current = null
      void saveRumbleIntensity(rumbleIntensityLatestValue.current)
    }, 500)
  }

  const handleTestRumble = async () => {
    clearPendingRumbleIntensitySave()
    setTestingRumble(true)
    setRumbleMessage(null)
    setRumbleMessageKind(null)
    try {
      const success = await testRumble()
      setRumbleMessage(success ? 'Sent a test rumble event.' : 'Failed to send a test rumble event.')
      setRumbleMessageKind(success ? 'success' : 'error')
    } catch (error) {
      setRumbleMessage(`Failed to send a test rumble event: ${String(error)}`)
      setRumbleMessageKind('error')
    } finally {
      setTestingRumble(false)
    }
  }

  const handleMissingGlyphFixTrackpadsChange = async (disabled: boolean) => {
    if (!activeGame || !isMissingGlyphFixEnabled) {
      return
    }

    setSavingMissingGlyphFixTrackpads(true)
    try {
      const nextSettings = await setMissingGlyphFixTrackpadsDisabled(activeGame.appid, disabled)
      setSettings(nextSettings)
      await syncActiveGameTarget(activeGame.appid)
    } catch (error) {
      setStatus({
        state: 'failed',
        message: `Failed to update trackpad setting: ${String(error)}`,
      })
    } finally {
      setSavingMissingGlyphFixTrackpads(false)
    }
  }

  useEffect(() => {
    void loadAll()

    const updateActiveGame = () => {
      const nextActiveGame = getActiveGame()
      setActiveGame((currentGame) => (areGamesEqual(currentGame, nextActiveGame) ? currentGame : nextActiveGame))

      const nextActiveGameId = nextActiveGame?.appid ?? DEFAULT_APP_ID
      if (lastActiveGameId.current !== nextActiveGameId) {
        lastActiveGameId.current = nextActiveGameId
        void syncActiveGameTarget(nextActiveGameId)
      }
    }

    updateActiveGame()
    const activeGamePollInterval = window.setInterval(() => {
      updateActiveGame()
    }, ACTIVE_GAME_POLL_INTERVAL_MS)

    return () => {
      clearPendingRumbleIntensitySave()
      clearInterval(activeGamePollInterval)
    }
  }, [])

  return (
    <PanelSection title="Controller">
      <PanelSectionRow>
        <ToggleField
          label="Startup Target"
          checked={settings.startupApplyEnabled}
          onChange={(value: boolean) => void handleStartupToggleChange(value)}
          disabled={savingStartup}
          description={getStartupDescription(status, settings)}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label="Missing Glyph Fix"
          checked={isMissingGlyphFixEnabled}
          onChange={(value: boolean) => void handleMissingGlyphFixToggleChange(value)}
          disabled={!activeGame || savingMissingGlyphFix}
          description={getMissingGlyphFixDescription(activeGame)}
        />
      </PanelSectionRow>
      {activeGame && isMissingGlyphFixEnabled && (
        <PanelSectionRow>
          <ToggleField
            label="Disable Trackpads"
            checked={isTrackpadsDisabled}
            onChange={(value: boolean) => void handleMissingGlyphFixTrackpadsChange(value)}
            disabled={savingMissingGlyphFix || savingMissingGlyphFixTrackpads}
            description={DISABLE_TRACKPADS_DESCRIPTION}
          />
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        <ToggleField
          label="Vibration Intensity"
          checked={settings.rumbleEnabled}
          onChange={(value: boolean) => void handleRumbleToggleChange(value)}
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
              onChange={handleRumbleIntensityChange}
              disabled={savingRumble || !settings.rumbleEnabled || !settings.rumbleAvailable}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={() => void handleTestRumble()}
              disabled={savingRumble || testingRumble || !settings.rumbleEnabled || !settings.rumbleAvailable}
            >
              {testingRumble ? 'Testing Rumble...' : `Test ${rumbleIntensityDraft} Rumble`}
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
    </PanelSection>
  )
}

export default definePlugin(() => {
  return {
    name: 'DeckyZone',
    titleView: <div className={staticClasses.Title}>DeckyZone</div>,
    content: <Content />,
    icon: <FaSlidersH />,
    onDismount() {
      console.log('DeckyZone unloaded')
    },
  }
})
