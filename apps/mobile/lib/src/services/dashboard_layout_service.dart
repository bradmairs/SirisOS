import 'package:shared_preferences/shared_preferences.dart';

import '../models/mission_control_widget.dart';

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

  static List<String> get defaultOrder => MissionControlWidgetRegistry.definitions
      .map((definition) => definition.id)
      .toList(growable: false);

  Future<List<DashboardWidgetPreference>> load() async {
    final preferences = await SharedPreferences.getInstance();
    final savedOrder = preferences.getStringList(_orderKey) ?? const <String>[];
    final hidden =
        (preferences.getStringList(_hiddenKey) ?? const <String>[]).toSet();

    final order = <String>[
      ...savedOrder.where(defaultOrder.contains),
      ...defaultOrder.where((id) => !savedOrder.contains(id)),
    ];

    return order.map((id) {
      final definition = MissionControlWidgetRegistry.definitionFor(id);
      final savedSize = preferences.getString('$_sizeKeyPrefix$id');
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
      MissionControlWidgetRegistry.definitions
          .map(
            (definition) => DashboardWidgetPreference(
              id: definition.id,
              visible: true,
              size: definition.defaultSize,
            ),
          )
          .toList(growable: false);
}
