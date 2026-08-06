import 'package:shared_preferences/shared_preferences.dart';

class DashboardWidgetPreference {
  const DashboardWidgetPreference({required this.id, required this.visible});

  final String id;
  final bool visible;

  DashboardWidgetPreference copyWith({bool? visible}) =>
      DashboardWidgetPreference(id: id, visible: visible ?? this.visible);
}

class DashboardLayoutService {
  static const _orderKey = 'dashboard_widget_order_v1';
  static const _hiddenKey = 'dashboard_hidden_widgets_v1';

  static const defaultOrder = <String>[
    'homelab',
    'running',
    'gym',
    'system',
    'activity',
    'briefing',
  ];

  Future<List<DashboardWidgetPreference>> load() async {
    final preferences = await SharedPreferences.getInstance();
    final savedOrder = preferences.getStringList(_orderKey) ?? const <String>[];
    final hidden = (preferences.getStringList(_hiddenKey) ?? const <String>[]).toSet();

    final order = <String>[
      ...savedOrder.where(defaultOrder.contains),
      ...defaultOrder.where((id) => !savedOrder.contains(id)),
    ];

    return order
        .map((id) => DashboardWidgetPreference(id: id, visible: !hidden.contains(id)))
        .toList(growable: false);
  }

  Future<void> save(List<DashboardWidgetPreference> widgets) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setStringList(_orderKey, widgets.map((item) => item.id).toList());
    await preferences.setStringList(
      _hiddenKey,
      widgets.where((item) => !item.visible).map((item) => item.id).toList(),
    );
  }

  Future<void> reset() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove(_orderKey);
    await preferences.remove(_hiddenKey);
  }
}
