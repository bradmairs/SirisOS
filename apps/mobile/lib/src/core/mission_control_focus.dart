import '../services/dashboard_layout_service.dart';

enum MissionControlFocus { all, work, home, fitness, travel }

class MissionControlFocusEngine {
  const MissionControlFocusEngine();

  List<DashboardWidgetPreference> apply(
    List<DashboardWidgetPreference> widgets,
    MissionControlFocus focus,
  ) {
    if (focus == MissionControlFocus.all) return widgets;

    final preferredIds = switch (focus) {
      MissionControlFocus.all => const <String>[],
      MissionControlFocus.work => const <String>[
          'siris.score',
          'siris.briefing',
          'activity.timeline',
          'system.summary',
          'homelab.summary',
        ],
      MissionControlFocus.home => const <String>[
          'homelab.summary',
          'system.summary',
          'siris.score',
          'siris.briefing',
          'activity.timeline',
        ],
      MissionControlFocus.fitness => const <String>[
          'running.summary',
          'gym.summary',
          'siris.score',
          'siris.briefing',
          'activity.timeline',
        ],
      MissionControlFocus.travel => const <String>[
          'siris.briefing',
          'siris.score',
          'activity.timeline',
          'system.summary',
        ],
    };

    final byId = <String, DashboardWidgetPreference>{
      for (final widget in widgets) widget.id: widget,
    };
    return preferredIds
        .map((id) => byId[id])
        .whereType<DashboardWidgetPreference>()
        .toList(growable: false);
  }
}
