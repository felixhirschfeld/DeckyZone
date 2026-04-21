export type PluginStatus = {
  state: string
  message: string
}

export type ControllerMode = 'gamepad' | 'desktop'
export type TrackpadMode = 'default' | 'disabled' | 'directional_buttons'

export type CleanupStepResult = {
  name: string
  ok: boolean
  changed: boolean
  message: string
}

export type PerGameRemapTarget =
  | 'none'
  | 'a'
  | 'b'
  | 'x'
  | 'y'
  | 'select'
  | 'start'
  | 'lb'
  | 'rb'
  | 'lt'
  | 'rt'
  | 'ls'
  | 'rs'
  | 'dpad_up'
  | 'dpad_down'
  | 'dpad_left'
  | 'dpad_right'

export type DebugInfoSnapshot = {
  deviceIdentity: {
    vendorName: string | null
    productName: string | null
    boardName: string | null
    boardVendor: string | null
    supportedDevice: boolean
    dmiPaths: string[]
  }
  osContext: {
    prettyName: string | null
    kernelRelease: string | null
    osReleaseCandidatePaths: string[]
  }
  inputPlumber: {
    available: boolean
    version: string | null
    profileName: string | null
    profilePath: string | null
    controllerMode: ControllerMode | null
    controllerModeAvailable: boolean
    targetGamepadPresent: boolean
    targetGamepadPath: string | null
    keyboardPresent: boolean
    keyboardPath: string | null
    controllerRuntimeState: string
    compositeDeviceObjectPath: string
  }
  zotacZoneKernelDrivers: {
    zotacZonePlatformLoaded: boolean
    zotacZonePlatformPath: string
    zotacZoneHidLoaded: boolean
    zotacZoneHidPath: string
    firmwareAttributesClassLoaded: boolean
    firmwareAttributesClassPath: string
    firmwareAttributesNodePresent: boolean
    firmwareAttributesNodePath: string
    hidConfigNodePath: string | null
    hidConfigSearchRoot: string
    hidConfigMatchMarker: string
  }
  gamescope: {
    version: string | null
    builtInAvailable: boolean
    managedProfileInstalled: boolean
    greenTintFixEnabled: boolean
    verificationState: string
    baseAssetAvailable: boolean
    greenTintAssetAvailable: boolean
    builtInCandidatePaths: string[]
    managedProfilePath: string
    baseAssetPath: string
    greenTintAssetPath: string
  }
  deckyZoneStatus: {
    message: string
  }
}

export type PerGameSettings = {
  enabled: boolean
  buttonPromptFixEnabled: boolean
  trackpadMode: TrackpadMode
  rumbleEnabled: boolean
  rumbleIntensity: number
  m1RemapTarget: PerGameRemapTarget
  m2RemapTarget: PerGameRemapTarget
}

export type ActiveGame = {
  appid: string
  display_name: string
  icon_data?: string
  icon_data_format?: string
  icon_hash?: string
  local_cache_version?: number | string
}

export type PluginSettings = {
  startupApplyEnabled: boolean
  controllerMode: ControllerMode | null
  controllerModeAvailable: boolean
  homeButtonEnabled: boolean
  brightnessDialFixEnabled: boolean
  trackpadMode: TrackpadMode
  zotacGlyphsEnabled: boolean
  gamescopeZotacProfileBuiltIn: boolean
  gamescopeZotacProfileInstalled: boolean
  gamescopeGreenTintFixEnabled: boolean
  gamescopeZotacProfileTargetPath: string
  gamescopeZotacProfileVerificationState: string
  inputplumberAvailable: boolean
  pluginVersionNum?: string
  rumbleEnabled: boolean
  rumbleIntensity: number
  rumbleAvailable: boolean
  perGameSettings: Record<string, PerGameSettings>
}

export type PluginResetResult = {
  ok: boolean
  settings: PluginSettings
  status: PluginStatus
  steps: CleanupStepResult[]
}
