import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  Router,
  SliderField,
  gamepadDialogClasses,
  staticClasses,
  SteamSpinner,
  ToggleField,
} from '@decky/ui'
import { addEventListener, callable, definePlugin, removeEventListener } from '@decky/api'
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
  brightnessDialFixEnabled: boolean
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

type BrightnessDialDirection = 'up' | 'down'
type ActiveGameChangedHandler = (newGame: ActiveGame | null, oldGame: ActiveGame | null) => void
type UnregisterFn = () => void
type SteamInputDiagnosticAppDetails = {
  bShowControllerConfig?: boolean
  eEnableThirdPartyControllerConfiguration?: number
  eSteamInputControllerMask?: number
}
type BootstrapSnapshot = {
  status: PluginStatus
  settings: PluginSettings
}
type BootstrapState = { state: 'loading' } | { state: 'ready'; snapshot: BootstrapSnapshot } | { state: 'error'; message: string }
type SteamInputDiagnosticState =
  | { state: 'idle' }
  | { state: 'loading'; appId: string }
  | { state: 'ready'; appId: string; details: SteamInputDiagnosticAppDetails }
  | { state: 'unavailable'; appId: string; message: string }
type SteamAppsClient = {
  GetCachedAppDetails?: (appId: number) => Promise<unknown>
  RegisterForAppDetails?: (appId: number, callback: (details: unknown) => void) => { unregister?: () => void }
}

const getStatus = callable<[], PluginStatus>('get_status')
const getSettings = callable<[], PluginSettings>('get_settings')
const setStartupApplyEnabled = callable<[boolean], PluginSettings>('set_startup_apply_enabled')
const setBrightnessDialFixEnabled = callable<[boolean], PluginSettings>('set_brightness_dial_fix_enabled')
const setMissingGlyphFixEnabled = callable<[string, boolean], PluginSettings>('set_missing_glyph_fix_enabled')
const setMissingGlyphFixTrackpadsDisabled = callable<[string, boolean], PluginSettings>('set_missing_glyph_fix_trackpads_disabled')
const syncMissingGlyphFixTarget = callable<[string], boolean>('sync_missing_glyph_fix_target')
const setRumbleEnabled = callable<[boolean], PluginSettings>('set_rumble_enabled')
const setRumbleIntensity = callable<[number], PluginSettings>('set_rumble_intensity')
const testRumble = callable<[], boolean>('test_rumble')

const DEFAULT_APP_ID = '0'
const ACTIVE_GAME_POLL_INTERVAL_MS = 1000
const DEFAULT_STARTUP_DESCRIPTION = 'Restores the Zotac controller after boot and enables the right brightness dial.'
const DEFAULT_BRIGHTNESS_DIAL_FIX_DESCRIPTION = 'Enable the right dial brightness.'
const DEFAULT_RUMBLE_DESCRIPTION = 'Change and test vibration intensity.'
const RUMBLE_UNAVAILABLE_MESSAGE = 'Rumble device is not available.'
const NO_ACTIVE_GAME_GLYPH_FIX_DESCRIPTION = 'Launch a game to enable this per-game Xbox Elite Mode.'
const DISABLE_TRACKPADS_DESCRIPTION = 'Turns off the trackpads while this glyph fix is active for the current game.'
const STEAM_INPUT_DIAGNOSTIC_UNAVAILABLE_MESSAGE = 'Steam Input state unavailable.'
const BRIGHTNESS_DIAL_FIX_STEP = 5

let brightnessDialFixEnabled = false
let currentBrightnessPercent = 50
let brightnessChangeRegistration: { unregister?: () => void } | null = null
let brightnessDialFixEventListener: ((direction: BrightnessDialDirection) => void) | null = null
let bootstrapState: BootstrapState = { state: 'loading' }
let bootstrapPromise: Promise<void> | null = null

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

function getBrightnessDialFixDescription(settings: PluginSettings) {
  if (!settings.inputplumberAvailable) {
    return 'InputPlumber is not available.'
  }

  return DEFAULT_BRIGHTNESS_DIAL_FIX_DESCRIPTION
}

function clampBrightnessPercent(value: number) {
  return Math.min(100, Math.max(0, value))
}

function setBrightnessDialFixRuntimeEnabled(enabled: boolean) {
  brightnessDialFixEnabled = enabled
}

function applyBrightnessDialDelta(delta: number) {
  if (!delta) {
    return
  }

  if (!window.SteamClient?.System?.Display?.SetBrightness) {
    return
  }

  const nextBrightness = clampBrightnessPercent(currentBrightnessPercent + delta)
  if (nextBrightness === currentBrightnessPercent) {
    return
  }

  currentBrightnessPercent = nextBrightness
  // Prefer SteamClient for the SteamOS path. If this ever proves insufficient,
  // a future fallback could use /sys/class/backlight or a gamescope-level path.
  window.SteamClient.System.Display.SetBrightness(nextBrightness / 100)
}

function registerBrightnessDialFixListeners() {
  if (!brightnessChangeRegistration && window.SteamClient?.System?.Display?.RegisterForBrightnessChanges) {
    brightnessChangeRegistration = window.SteamClient.System.Display.RegisterForBrightnessChanges((data: { flBrightness: number }) => {
      currentBrightnessPercent = clampBrightnessPercent(data.flBrightness * 100)
    })
  }

  if (!brightnessDialFixEventListener) {
    brightnessDialFixEventListener = (direction: BrightnessDialDirection) => {
      if (!brightnessDialFixEnabled) {
        return
      }

      applyBrightnessDialDelta(direction === 'up' ? BRIGHTNESS_DIAL_FIX_STEP : -BRIGHTNESS_DIAL_FIX_STEP)
    }

    addEventListener<[BrightnessDialDirection]>('brightness_dial_input', brightnessDialFixEventListener)
  }
}

function cleanupBrightnessDialFixListeners() {
  if (brightnessDialFixEventListener) {
    removeEventListener<[BrightnessDialDirection]>('brightness_dial_input', brightnessDialFixEventListener)
    brightnessDialFixEventListener = null
  }

  brightnessChangeRegistration?.unregister?.()
  brightnessChangeRegistration = null
}

function getBootstrapState() {
  return bootstrapState
}

function getBootstrapStatus() {
  return bootstrapState.state === 'ready' ? bootstrapState.snapshot.status : null
}

function getBootstrapSettings() {
  return bootstrapState.state === 'ready' ? bootstrapState.snapshot.settings : null
}

function setBootstrapSnapshot(nextStatus: PluginStatus, nextSettings: PluginSettings) {
  setBrightnessDialFixRuntimeEnabled(nextSettings.brightnessDialFixEnabled)
  bootstrapState = {
    state: 'ready',
    snapshot: {
      status: nextStatus,
      settings: nextSettings,
    },
  }
}

function cacheBootstrapStatus(nextStatus: PluginStatus) {
  if (bootstrapState.state !== 'ready') {
    return
  }

  bootstrapState = {
    state: 'ready',
    snapshot: {
      ...bootstrapState.snapshot,
      status: nextStatus,
    },
  }
}

function cacheBootstrapSettings(nextSettings: PluginSettings) {
  setBrightnessDialFixRuntimeEnabled(nextSettings.brightnessDialFixEnabled)

  if (bootstrapState.state !== 'ready') {
    return
  }

  bootstrapState = {
    state: 'ready',
    snapshot: {
      ...bootstrapState.snapshot,
      settings: nextSettings,
    },
  }
}

function startBootstrap() {
  if (bootstrapPromise !== null) {
    return bootstrapPromise
  }

  bootstrapState = { state: 'loading' }
  bootstrapPromise = Promise.all([getStatus(), getSettings()])
    .then(([nextStatus, nextSettings]) => {
      setBootstrapSnapshot(nextStatus, nextSettings)
    })
    .catch((error) => {
      bootstrapState = {
        state: 'error',
        message: `Failed to load plugin state: ${String(error)}`,
      }
    })

  return bootstrapPromise
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

class RunningApps {
  private static listeners: ActiveGameChangedHandler[] = []
  private static intervalId: ReturnType<typeof setInterval> | null = null
  private static lastActiveGame: ActiveGame | null = getActiveGame()
  private static lastAppId = RunningApps.lastActiveGame?.appid ?? DEFAULT_APP_ID

  private static pollActive() {
    const nextActiveGame = getActiveGame()
    const nextAppId = nextActiveGame?.appid ?? DEFAULT_APP_ID

    if (this.lastAppId !== nextAppId) {
      const previousActiveGame = this.lastActiveGame
      this.lastActiveGame = nextActiveGame
      this.lastAppId = nextAppId
      this.listeners.forEach((listener) => listener(nextActiveGame, previousActiveGame))
      return
    }

    this.lastActiveGame = nextActiveGame
  }

  static register() {
    this.lastActiveGame = getActiveGame()
    this.lastAppId = this.lastActiveGame?.appid ?? DEFAULT_APP_ID

    if (this.intervalId === null) {
      this.intervalId = setInterval(() => {
        this.pollActive()
      }, ACTIVE_GAME_POLL_INTERVAL_MS)
    }
  }

  static unregister() {
    if (this.intervalId !== null) {
      clearInterval(this.intervalId)
      this.intervalId = null
    }

    this.listeners = []
    this.lastActiveGame = null
    this.lastAppId = DEFAULT_APP_ID
  }

  static listenActiveChange(fn: ActiveGameChangedHandler): UnregisterFn {
    this.listeners.push(fn)
    return () => {
      this.listeners = this.listeners.filter((listener) => listener !== fn)
    }
  }

  static active() {
    return this.lastActiveGame?.appid ?? DEFAULT_APP_ID
  }

  static activeAppInfo() {
    return this.lastActiveGame
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
        {`Fixes missing glyphs for ${activeGame.display_name}. This setting is per-game.`}
      </div>
    </div>
  )
}

function normalizeSteamInputDiagnosticDetails(rawDetails: unknown): SteamInputDiagnosticAppDetails | null {
  let parsedDetails = rawDetails

  if (typeof parsedDetails === 'string') {
    try {
      parsedDetails = JSON.parse(parsedDetails)
    } catch {
      return null
    }
  }

  if (!parsedDetails || typeof parsedDetails !== 'object') {
    return null
  }

  const details = parsedDetails as Record<string, unknown>
  const thirdPartyControllerConfiguration = details.eEnableThirdPartyControllerConfiguration
  const steamInputControllerMask = details.eSteamInputControllerMask
  const showControllerConfig = details.bShowControllerConfig

  if (
    typeof thirdPartyControllerConfiguration !== 'number' &&
    typeof steamInputControllerMask !== 'number' &&
    typeof showControllerConfig !== 'boolean'
  ) {
    return null
  }

  return {
    bShowControllerConfig: typeof showControllerConfig === 'boolean' ? showControllerConfig : undefined,
    eEnableThirdPartyControllerConfiguration:
      typeof thirdPartyControllerConfiguration === 'number' ? thirdPartyControllerConfiguration : undefined,
    eSteamInputControllerMask: typeof steamInputControllerMask === 'number' ? steamInputControllerMask : undefined,
  }
}

function getSteamInputDiagnosticStatus(details: SteamInputDiagnosticAppDetails) {
  switch (details.eEnableThirdPartyControllerConfiguration) {
    case 0:
      return details.bShowControllerConfig === false ? 'Steam Input disabled' : 'Mixed or unknown Steam Input state'
    case 1:
      return details.bShowControllerConfig === true ? 'Steam Input enabled/default' : 'Mixed or unknown Steam Input state'
    case 2:
      return 'Steam Input enabled/forced'
    default:
      return 'Mixed or unknown Steam Input state'
  }
}

async function syncActiveGameTarget(appId: string) {
  try {
    await syncMissingGlyphFixTarget(appId)
  } catch (error) {
    console.error('Failed to sync missing glyph fix target', error)
  }
}

function Content() {
  const [bootstrap, setBootstrap] = useState<BootstrapState>(getBootstrapState())
  const [status, setStatus] = useState<PluginStatus | null>(() => getBootstrapStatus())
  const [settings, setSettings] = useState<PluginSettings | null>(() => getBootstrapSettings())
  const [activeGame, setActiveGame] = useState<ActiveGame | null>(getActiveGame())
  const [rumbleIntensityDraft, setRumbleIntensityDraft] = useState(75)
  const [savingStartup, setSavingStartup] = useState(false)
  const [savingBrightnessDialFix, setSavingBrightnessDialFix] = useState(false)
  const [savingMissingGlyphFix, setSavingMissingGlyphFix] = useState(false)
  const [savingMissingGlyphFixTrackpads, setSavingMissingGlyphFixTrackpads] = useState(false)
  const [savingRumble, setSavingRumble] = useState(false)
  const [testingRumble, setTestingRumble] = useState(false)
  const [rumbleMessage, setRumbleMessage] = useState<string | null>(null)
  const [rumbleMessageKind, setRumbleMessageKind] = useState<'success' | 'error' | null>(null)
  const [steamInputDiagnostic, setSteamInputDiagnostic] = useState<SteamInputDiagnosticState>({ state: 'idle' })
  const rumbleIntensityLatestValue = useRef(75)
  const rumbleIntensitySaveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearPendingRumbleIntensitySave = () => {
    if (rumbleIntensitySaveTimeout.current !== null) {
      clearTimeout(rumbleIntensitySaveTimeout.current)
      rumbleIntensitySaveTimeout.current = null
    }
  }

  const loadStatus = async () => {
    const nextStatus = await getStatus()
    cacheBootstrapStatus(nextStatus)
    setBootstrap(getBootstrapState())
    setStatus(nextStatus)
  }

  const handleStartupToggleChange = async (enabled: boolean) => {
    setSavingStartup(true)
    try {
      const nextSettings = await setStartupApplyEnabled(enabled)
      cacheBootstrapSettings(nextSettings)
      setBootstrap(getBootstrapState())
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

  const handleBrightnessDialFixToggleChange = async (enabled: boolean) => {
    setSavingBrightnessDialFix(true)
    try {
      const nextSettings = await setBrightnessDialFixEnabled(enabled)
      cacheBootstrapSettings(nextSettings)
      setBootstrap(getBootstrapState())
      setSettings(nextSettings)
      setBrightnessDialFixRuntimeEnabled(nextSettings.brightnessDialFixEnabled)
    } catch (error) {
      setStatus({
        state: 'failed',
        message: `Failed to update brightness dial fix: ${String(error)}`,
      })
    } finally {
      setSavingBrightnessDialFix(false)
    }
  }

  const handleMissingGlyphFixToggleChange = async (enabled: boolean) => {
    if (!activeGame) {
      return
    }

    setSavingMissingGlyphFix(true)
    try {
      const nextSettings = await setMissingGlyphFixEnabled(activeGame.appid, enabled)
      cacheBootstrapSettings(nextSettings)
      setBootstrap(getBootstrapState())
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
      cacheBootstrapSettings(nextSettings)
      setBootstrap(getBootstrapState())
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
      const mergedSettings = settings
        ? {
            ...settings,
            rumbleIntensity: nextSettings.rumbleIntensity,
            rumbleAvailable: nextSettings.rumbleAvailable,
          }
        : nextSettings
      cacheBootstrapSettings(mergedSettings)
      setBootstrap(getBootstrapState())
      setSettings(mergedSettings)
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
      cacheBootstrapSettings(nextSettings)
      setBootstrap(getBootstrapState())
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
    const syncBootstrapIntoLocalState = () => {
      const nextBootstrap = getBootstrapState()
      setBootstrap(nextBootstrap)
      if (nextBootstrap.state !== 'ready') {
        return
      }

      setStatus(nextBootstrap.snapshot.status)
      setSettings(nextBootstrap.snapshot.settings)
      setRumbleIntensityDraft(nextBootstrap.snapshot.settings.rumbleIntensity)
      rumbleIntensityLatestValue.current = nextBootstrap.snapshot.settings.rumbleIntensity
      if (!nextBootstrap.snapshot.settings.rumbleAvailable) {
        setRumbleMessage(null)
        setRumbleMessageKind(null)
      }
    }

    syncBootstrapIntoLocalState()
    void startBootstrap().then(() => {
      syncBootstrapIntoLocalState()
    })
    setActiveGame((currentGame) => {
      const nextActiveGame = RunningApps.activeAppInfo() ?? getActiveGame()
      return areGamesEqual(currentGame, nextActiveGame) ? currentGame : nextActiveGame
    })
    const unregisterActiveGameListener = RunningApps.listenActiveChange((nextActiveGame) => {
      setActiveGame((currentGame) => (areGamesEqual(currentGame, nextActiveGame) ? currentGame : nextActiveGame))
    })

    return () => {
      clearPendingRumbleIntensitySave()
      unregisterActiveGameListener()
    }
  }, [])

  const activeGameGlyphFixSettings = activeGame && settings ? settings.missingGlyphFixGames[activeGame.appid] : undefined
  const isMissingGlyphFixEnabled = Boolean(activeGameGlyphFixSettings)
  const isTrackpadsDisabled = activeGameGlyphFixSettings?.disableTrackpads ?? true

  useEffect(() => {
    if (!activeGame || !isMissingGlyphFixEnabled) {
      setSteamInputDiagnostic({ state: 'idle' })
      return
    }

    const steamApps = window.SteamClient?.Apps as SteamAppsClient | undefined
    const numericAppId = Number(activeGame.appid)

    if (!steamApps?.GetCachedAppDetails || Number.isNaN(numericAppId)) {
      setSteamInputDiagnostic({
        state: 'unavailable',
        appId: activeGame.appid,
        message: STEAM_INPUT_DIAGNOSTIC_UNAVAILABLE_MESSAGE,
      })
      return
    }

    let cancelled = false
    setSteamInputDiagnostic({ state: 'loading', appId: activeGame.appid })

    const updateDiagnosticDetails = (rawDetails: unknown) => {
      if (cancelled) {
        return
      }

      const nextDetails = normalizeSteamInputDiagnosticDetails(rawDetails)
      if (!nextDetails) {
        setSteamInputDiagnostic({
          state: 'unavailable',
          appId: activeGame.appid,
          message: STEAM_INPUT_DIAGNOSTIC_UNAVAILABLE_MESSAGE,
        })
        return
      }

      setSteamInputDiagnostic({
        state: 'ready',
        appId: activeGame.appid,
        details: nextDetails,
      })
    }

    void steamApps
      .GetCachedAppDetails(numericAppId)
      .then((details) => {
        updateDiagnosticDetails(details)
      })
      .catch(() => {
        if (cancelled) {
          return
        }

        setSteamInputDiagnostic({
          state: 'unavailable',
          appId: activeGame.appid,
          message: STEAM_INPUT_DIAGNOSTIC_UNAVAILABLE_MESSAGE,
        })
      })

    const registration = steamApps.RegisterForAppDetails?.(numericAppId, (details) => {
      updateDiagnosticDetails(details)
    })

    return () => {
      cancelled = true
      registration?.unregister?.()
    }
  }, [activeGame, isMissingGlyphFixEnabled])

  if (bootstrap.state === 'loading') {
    return (
      <PanelSection title="Controller">
        <PanelSectionRow>
          <SteamSpinner />
        </PanelSectionRow>
      </PanelSection>
    )
  }

  if (bootstrap.state === 'error') {
    return (
      <PanelSection title="Controller">
        <PanelSectionRow>
          <div style={{ color: 'red' }}>{bootstrap.message}</div>
        </PanelSectionRow>
      </PanelSection>
    )
  }

  if (!status || !settings) {
    return (
      <PanelSection title="Controller">
        <PanelSectionRow>
          <SteamSpinner />
        </PanelSectionRow>
      </PanelSection>
    )
  }

  const shouldShowSteamInputDisabledWarning =
    steamInputDiagnostic.state === 'ready' && getSteamInputDiagnosticStatus(steamInputDiagnostic.details) === 'Steam Input disabled'

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
          label="Brightness Dial"
          checked={settings.brightnessDialFixEnabled}
          onChange={(value: boolean) => void handleBrightnessDialFixToggleChange(value)}
          disabled={savingBrightnessDialFix}
          description={getBrightnessDialFixDescription(settings)}
        />
      </PanelSectionRow>
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
      <PanelSectionRow>
        <ToggleField
          label="Xbox Elite Mode"
          checked={isMissingGlyphFixEnabled}
          onChange={(value: boolean) => void handleMissingGlyphFixToggleChange(value)}
          disabled={!activeGame || savingMissingGlyphFix}
          description={getMissingGlyphFixDescription(activeGame)}
        />
      </PanelSectionRow>
      {activeGame && isMissingGlyphFixEnabled && shouldShowSteamInputDisabledWarning && (
        <PanelSectionRow>
          <div className={gamepadDialogClasses.FieldDescription}>Steam Input disabled</div>
        </PanelSectionRow>
      )}
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
    </PanelSection>
  )
}

export default definePlugin(() => {
  registerBrightnessDialFixListeners()
  RunningApps.register()
  void startBootstrap()
  const unregisterActiveGameSync = RunningApps.listenActiveChange((nextActiveGame) => {
    void syncActiveGameTarget(nextActiveGame?.appid ?? DEFAULT_APP_ID)
  })
  void syncActiveGameTarget(RunningApps.active())

  return {
    name: 'DeckyZone',
    titleView: <div className={staticClasses.Title}>DeckyZone</div>,
    content: <Content />,
    icon: <FaSlidersH />,
    onDismount() {
      unregisterActiveGameSync()
      RunningApps.unregister()
      cleanupBrightnessDialFixListeners()
      console.log('DeckyZone unloaded')
    },
  }
})
