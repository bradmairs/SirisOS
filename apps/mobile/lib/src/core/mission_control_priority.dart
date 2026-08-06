import '../models/dashboard_summary.dart';
import '../models/mission_control_widget.dart';

/// Applies transient display priority without mutating the user's saved layout.
class MissionControlPriorityEngine {
  const MissionControlPriorityEngine();

  List<DashboardWidgetPreference> arrange(
    List<DashboardWidgetPreference> layout,
    DashboardSummary dashboard, {
    required bool adaptive,
  }) {
    final visible = layout.where((item) => item.visible).toList(growable: false);
    if (!adaptive) return visible;

    final priority = <String, int>{
      'siris.score': 100,
      'siris.briefing': 95,
      'activity.timeline': 20,
    };

    _raiseForStatus(priority, 'homelab.summary', dashboard.homelab.status);
    _raiseForStatus(priority, 'system.summary', dashboard.system.status);
    _raiseForStatus(priority, 'running.summary', dashboard.running.status);
    _raiseForStatus(priority, 'gym.summary', dashboard.gym.status);

    final indexed = visible.indexed.toList(growable: false)
      ..sort((a, b) {
        final aPriority = priority[a.$2.id] ?? 40;
        final bPriority = priority[b.$2.id] ?? 40;
        final byPriority = bPriority.compareTo(aPriority);
        return byPriority != 0 ? byPriority : a.$1.compareTo(b.$1);
      });

    return indexed.map((entry) {
      final item = entry.$2;
      final score = priority[item.id] ?? 40;
      if (score < 80 || item.size == MissionControlWidgetSize.wide) return item;
      return item.copyWith(size: MissionControlWidgetSize.wide);
    }).toList(growable: false);
  }

  static void _raiseForStatus(
    Map<String, int> priority,
    String widgetId,
    String status,
  ) {
    final normalized = status.toLowerCase();
    if (normalized == 'critical' || normalized == 'error') {
      priority[widgetId] = 110;
    } else if (normalized == 'warning' || normalized == 'unhealthy') {
      priority[widgetId] = 90;
    } else {
      priority[widgetId] = 50;
    }
  }
}
