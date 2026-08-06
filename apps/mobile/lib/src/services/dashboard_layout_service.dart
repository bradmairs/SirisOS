import 'package:shared_preferences/shared_preferences.dart';

import '../models/mission_control_widget.dart';
import '../modules/app_widget_registry.dart';

class DashboardWidgetPreference {
  const DashboardWidgetPreference({
    required this.id,
    required this.visible,
    required this.size,
  });

  final String id;
  final bool visible;
  final MissionControlWidgetSize size;

  DashboardWidgetPreference copyWith({
    bool? visible,
    MissionControlWidgetSize? size,
  }) =>
      DashboardWidgetPreference(
        id: id,
        visible: visible ?? this.visible,
        size: size ?? this.size,
      );
}

class DashboardLayoutService {
  static const _orderKey = 'dashboard_widget_order_v1';
  static const _hiddenKey = 'dashboard_hidden_widgets_v1';
  static const _sizeKeyPrefix = 'mission_control_widget_size_';

  static List<String> get defaultOrder => AppWidgetRegistry.definitions
      .map((definition) => definition.id)
      .toList(growable: false);

  Future<List<DashboardWidgetPreference>> load() async {
    final preferences = await SharedPreferences.getInstance();
    final savedOrder = preferences.getStringList(_orderKey) ?? const <String>[];
    final savedHidden =
        preferences.getStringList(_hiddenKey) ?? const <String>[];

    final canonicalSavedOrder = savedOrder
        .map(AppWidgetRegistry.canonicalIdFor)
        .where(defaultOrder.contains)
        .toList(growable: false);
    final hidden = savedHidden
        .map(AppWidgetRegistry.canonicalIdFor)
        .toSet();

    final order = <String>[
      ...canonicalSavedOrder,
      ...defaultOrder.where((id) => !canonicalSavedOrder.contains(id)),
    ];

    return order.map((id) {
      final definition = AppWidgetRegistry.definitionFor(id);
      final savedSize = preferences.getString('$_sizeKeyPrefix$id') ??
          _legacySavedSize(preferences, id);
      return DashboardWidgetPreference(
        id: id,
        visible: !hidden.contains(id),
        size: MissionControlWidgetSize.values.firstWhere(
          (size) => size.name == savedSize,
          orElse: () => definition.defaultSize,
        ),
      );
    }).toList(growable: false);
  }

  String? _legacySavedSize(SharedPreferences preferences, String id) {
    for (final entry in const {
      'briefing': 'siris.briefing',
      'homelab': 'homelab.summary',
      'running': 'running.summary',
      'gym': 'gym.summary',
      'system': 'system.summary',
      'activity': 'activity.timeline',
    }.entries) {
      if (entry.value == id) {
        return preferences.getString('$_sizeKeyPrefix${entry.key}');
      }
    }
    return null;
  }

  Future<void> save(List<DashboardWidgetPreference> widgets) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setStringList(
      _orderKey,
      widgets.map((item) => item.id).toList(),
    );
    await preferences.setStringList(
      _hiddenKey,
      widgets.where((item) => !item.visible).map((item) => item.id).toList(),
    );
    for (final widget in widgets) {
      await preferences.setString('$_sizeKeyPrefix${widget.id}', widget.size.name);
    }
  }

  Future<void> reset() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove(_orderKey);
    await preferences.remove(_hiddenKey);
    for (final id in defaultOrder) {
      await preferences.remove('$_sizeKeyPrefix$id');
    }
  }

  static List<DashboardWidgetPreference> defaultLayout() =>
      AppWidgetRegistry.definitions
          .map(
            (definition) => DashboardWidgetPreference(
              id: definition.id,
              visible: true,
              size: definition.defaultSize,
            ),
          )
          .toList(growable: false);
}
