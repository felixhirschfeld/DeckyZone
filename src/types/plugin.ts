export type PluginStatus = {
  state: string
  message: string
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
