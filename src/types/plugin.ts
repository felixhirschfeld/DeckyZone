export type PluginStatus = {
  state: string
  message: string
}

export type SupportSnapshot = {
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
    profileName: string | null
    profilePath: string | null
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
    builtInAvailable: boolean
    managedProfileInstalled: boolean
    greenTintFixEnabled: boolean
    verificationState: string
    builtInCandidatePaths: string[]
    managedProfilePath: string
    legacyManagedBaseProfilePath: string
    legacyManagedGreenTintProfilePath: string
    assetBaseProfilePath: string
    assetGreenTintProfilePath: string
  }
  deckyZoneStatus: {
    message: string
  }
}

export type MissingGlyphFixGameSettings = {
  disableTrackpads: boolean
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
  homeButtonEnabled: boolean
  brightnessDialFixEnabled: boolean
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
  missingGlyphFixGames: Record<string, MissingGlyphFixGameSettings>
}
