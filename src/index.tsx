import {
  Navigation,
  PanelSection,
  PanelSectionRow,
  Router,
  SteamSpinner,
} from '@decky/ui'
import { addEventListener, callable, definePlugin, removeEventListener } from '@decky/api'
import { Fragment, useEffect, useState } from 'react'
import ControllerPanel from "./components/ControllerPanel"
import DisplayPanel from "./components/DisplayPanel"
import ErrorBoundary from "./components/ErrorBoundary"
import InterfacePanel from "./components/InterfacePanel"
import QuickAccessTitleView from "./components/QuickAccessTitleView"
import TroubleshootingPanel from "./components/TroubleshootingPanel"
import UpdatesPanel from "./components/UpdatesPanel"
import ZotacIcon from "./components/ZotacIcon"
import { cleanupZotacGlyphsRuntime, syncStoredZotacGlyphsRuntimeEnabled } from "./glyphs/zotacGlyphRuntime"
import type { ActiveGame, PluginResetResult, PluginSettings, PluginStatus } from "./types/plugin"

type BrightnessDialDirection = 'up' | 'down'
type ActiveGameChangedHandler = (newGame: ActiveGame | null, oldGame: ActiveGame | null) => void
type UnregisterFn = () => void
type BootstrapSnapshot = {
  status: PluginStatus
  settings: PluginSettings
}
type BootstrapState = { state: 'loading' } | { state: 'ready'; snapshot: BootstrapSnapshot } | { state: 'error'; message: string }

const getStatus = callable<[], PluginStatus>('get_status')
const getSettings = callable<[], PluginSettings>('get_settings')
const resetPlugin = callable<[], PluginResetResult>('reset_plugin')
const syncPerGameTarget = callable<[string], boolean>('sync_per_game_target')

const DEFAULT_APP_ID = '0'
const ACTIVE_GAME_POLL_INTERVAL_MS = 1000
const BRIGHTNESS_DIAL_FIX_STEP = 5

let brightnessDialFixEnabled = false
let homeButtonEnabled = false
let currentBrightnessPercent = 50
let brightnessChangeRegistration: { unregister?: () => void } | null = null
let brightnessDialFixEventListener: ((direction: BrightnessDialDirection) => void) | null = null
let bootstrapState: BootstrapState = { state: 'loading' }
let bootstrapPromise: Promise<void> | null = null

function clampBrightnessPercent(value: number) {
  return Math.min(100, Math.max(0, value))
}

function setBrightnessDialFixRuntimeEnabled(enabled: boolean) {
  brightnessDialFixEnabled = enabled
}

function setHomeButtonRuntimeEnabled(enabled: boolean) {
  homeButtonEnabled = enabled
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
  setHomeButtonRuntimeEnabled(nextSettings.homeButtonEnabled)
  syncStoredZotacGlyphsRuntimeEnabled(nextSettings.zotacGlyphsEnabled)
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
  setHomeButtonRuntimeEnabled(nextSettings.homeButtonEnabled)
  syncStoredZotacGlyphsRuntimeEnabled(nextSettings.zotacGlyphsEnabled)

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

async function syncActiveGameTarget(appId: string) {
  try {
    const synced = await syncPerGameTarget(appId)
    if (!synced) {
      return null
    }
    const nextStatus = await getStatus()
    cacheBootstrapStatus(nextStatus)
    return nextStatus
  } catch (error) {
    console.error('Failed to sync per-game target', error)
  }
  return null
}

function Content() {
  const [bootstrap, setBootstrap] = useState<BootstrapState>(getBootstrapState())
  const [status, setStatus] = useState<PluginStatus | null>(() => getBootstrapStatus())
  const [settings, setSettings] = useState<PluginSettings | null>(() => getBootstrapSettings())
  const [activeGame, setActiveGame] = useState<ActiveGame | null>(getActiveGame())
  const [uiRevision, setUiRevision] = useState(0)

  const applySettingsUpdate = (nextSettings: PluginSettings) => {
    cacheBootstrapSettings(nextSettings)
    setBootstrap(getBootstrapState())
    setSettings(nextSettings)
  }

  const applyStatusUpdate = (nextStatus: PluginStatus) => {
    cacheBootstrapStatus(nextStatus)
    setBootstrap(getBootstrapState())
    setStatus(nextStatus)
  }

  const applySnapshotUpdate = (nextStatus: PluginStatus, nextSettings: PluginSettings) => {
    setBootstrapSnapshot(nextStatus, nextSettings)
    setBootstrap(getBootstrapState())
    setStatus(nextStatus)
    setSettings(nextSettings)
  }

  const refreshStatusAfterActiveGameSync = (appId: string) => {
    void syncActiveGameTarget(appId).then((nextStatus) => {
      if (nextStatus) {
        applyStatusUpdate(nextStatus)
      }
    })
  }

  const handleResetPlugin = async () => {
    let glyphCleanupFailed = false

    try {
      await cleanupZotacGlyphsRuntime()
    } catch {
      glyphCleanupFailed = true
    }

    const result = await resetPlugin()
    let nextStatus = result.status
    let nextSettings = result.settings

    try {
      ;[nextStatus, nextSettings] = await Promise.all([getStatus(), getSettings()])
    } catch (error) {
      console.error('Failed to refresh DeckyZone state after reset', error)
    }

    applySnapshotUpdate(nextStatus, nextSettings)
    setUiRevision((revision) => revision + 1)

    return {
      result,
      glyphCleanupFailed,
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
    }

    syncBootstrapIntoLocalState()
    void startBootstrap().then(() => {
      syncBootstrapIntoLocalState()
      refreshStatusAfterActiveGameSync(RunningApps.active())
    })
    setActiveGame((currentGame) => {
      const nextActiveGame = RunningApps.activeAppInfo() ?? getActiveGame()
      return areGamesEqual(currentGame, nextActiveGame) ? currentGame : nextActiveGame
    })
    const unregisterActiveGameListener = RunningApps.listenActiveChange((nextActiveGame) => {
      setActiveGame((currentGame) => (areGamesEqual(currentGame, nextActiveGame) ? currentGame : nextActiveGame))
      refreshStatusAfterActiveGameSync(nextActiveGame?.appid ?? DEFAULT_APP_ID)
    })

    return () => {
      unregisterActiveGameListener()
    }
  }, [])

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

  return (
    <Fragment key={`deckyzone-ui:${uiRevision}`}>
      <ErrorBoundary title="Controller">
        <ControllerPanel
          activeGame={activeGame}
          settings={settings}
          status={status}
          onSettingsChange={applySettingsUpdate}
          onStatusChange={applyStatusUpdate}
        />
      </ErrorBoundary>
      <ErrorBoundary title="Interface">
        <InterfacePanel
          settings={settings}
          onSettingsChange={applySettingsUpdate}
        />
      </ErrorBoundary>
      <ErrorBoundary title="Display">
        <DisplayPanel
          settings={settings}
          onSettingsChange={applySettingsUpdate}
        />
      </ErrorBoundary>
      <ErrorBoundary title="Troubleshooting">
        <TroubleshootingPanel
          onResetPlugin={handleResetPlugin}
        />
      </ErrorBoundary>
      <ErrorBoundary title="Updates">
        <UpdatesPanel
          installedVersionNum={settings.pluginVersionNum ?? ''}
        />
      </ErrorBoundary>
    </Fragment>
  )
}

export default definePlugin(() => {
  registerBrightnessDialFixListeners()
  RunningApps.register()
  void startBootstrap()
  const unregisterHomeNavigationListener = addEventListener('zotac_home_short_pressed', () => {
    if (!homeButtonEnabled) {
      return
    }

    Navigation.Navigate('/library/home')
    Navigation.CloseSideMenus()
  })
  const unregisterActiveGameSync = RunningApps.listenActiveChange((nextActiveGame) => {
    void syncActiveGameTarget(nextActiveGame?.appid ?? DEFAULT_APP_ID)
  })
  void syncActiveGameTarget(RunningApps.active())

  return {
    name: 'DeckyZone',
    titleView: <QuickAccessTitleView title="DeckyZone" />,
    content: <Content />,
    icon: <ZotacIcon />,
    onDismount() {
      removeEventListener('zotac_home_short_pressed', unregisterHomeNavigationListener)
      unregisterActiveGameSync()
      RunningApps.unregister()
      cleanupBrightnessDialFixListeners()
      void cleanupZotacGlyphsRuntime()
      console.log('DeckyZone unloaded')
    },
  }
})
