import 'package:shared_preferences/shared_preferences.dart';

class SirisCoreSettings {
  const SirisCoreSettings({
    required this.autoRefreshEnabled,
    required this.refreshMinutes,
    required this.enabledModules,
  });

  final bool autoRefreshEnabled;
  final int refreshMinutes;
  final Set<String> enabledModules;
}

class SirisSettingsService {
  static const _autoRefreshKey = 'siris.auto_refresh';
  static const _refreshMinutesKey = 'siris.refresh_minutes';
  static const _enabledModulesKey = 'siris.enabled_modules';

  Future<SirisCoreSettings> load({required Iterable<String> defaultModules}) async {
    final preferences = await SharedPreferences.getInstance();
    return SirisCoreSettings(
      autoRefreshEnabled: preferences.getBool(_autoRefreshKey) ?? true,
      refreshMinutes: (preferences.getInt(_refreshMinutesKey) ?? 5).clamp(1, 60),
      enabledModules: (preferences.getStringList(_enabledModulesKey) ??
              defaultModules.toList(growable: false))
          .toSet(),
    );
  }

  Future<void> setAutoRefreshEnabled(bool enabled) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setBool(_autoRefreshKey, enabled);
  }

  Future<void> setRefreshMinutes(int minutes) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setInt(_refreshMinutesKey, minutes.clamp(1, 60));
  }

  Future<void> setModuleEnabled(String moduleId, bool enabled) async {
    final preferences = await SharedPreferences.getInstance();
    final modules = (preferences.getStringList(_enabledModulesKey) ?? <String>[]).toSet();
    enabled ? modules.add(moduleId) : modules.remove(moduleId);
    await preferences.setStringList(_enabledModulesKey, modules.toList()..sort());
  }
}
