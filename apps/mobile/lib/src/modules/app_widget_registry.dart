import 'package:flutter/material.dart';

import '../core/briefing_engine.dart';
import '../models/dashboard_summary.dart';
import '../models/mission_control_widget.dart';
import '../widgets/activity_feed_panel.dart';
import '../widgets/dashboard_card.dart';
import '../widgets/dashboard_hero.dart';
import '../widgets/grafana_panel.dart';
import '../widgets/prometheus_panel.dart';
import '../widgets/siris_score_panel.dart';
import '../widgets/storage_panel.dart';
import '../widgets/synology_panel.dart';
import '../widgets/unifi_panel.dart';

class MissionControlWidgetContext {
  const MissionControlWidgetContext({required this.dashboard, required this.greeting});

  final DashboardSummary dashboard;
  final String greeting;
}

typedef MissionControlWidgetBuilder = Widget Function(MissionControlWidgetContext context);

class RegisteredMissionControlWidget {
  const RegisteredMissionControlWidget({required this.definition, required this.builder});

  final MissionControlWidgetDefinition definition;
  final MissionControlWidgetBuilder builder;
}

class AppWidgetRegistry {
  AppWidgetRegistry._();

  static final DeterministicBriefingEngine _briefingEngine = DeterministicBriefingEngine();

  static final List<RegisteredMissionControlWidget> registrations = [
    ..._sirisWidgets,
    ..._homelabWidgets,
    ..._runningWidgets,
    ..._gymWidgets,
    ..._systemWidgets,
    ..._activityWidgets,
  ];

  static List<MissionControlWidgetDefinition> get definitions => registrations
      .map((registration) => registration.definition)
      .toList(growable: false);

  static RegisteredMissionControlWidget? find(String id) {
    final canonicalId = canonicalIdFor(id);
    for (final registration in registrations) {
      if (registration.definition.id == canonicalId) return registration;
    }
    return null;
  }

  static MissionControlWidgetDefinition definitionFor(String id) =>
      find(id)?.definition ?? MissionControlWidgetDefinition(
        id: canonicalIdFor(id),
        moduleId: 'unknown',
        label: id,
        description: 'Mission Control widget',
        icon: Icons.widgets_rounded,
        defaultSize: MissionControlWidgetSize.standard,
      );

  static Widget build(String id, MissionControlWidgetContext context) =>
      find(id)?.builder(context) ?? const SizedBox.shrink();

  static String canonicalIdFor(String id) => _legacyIds[id] ?? id;

  static const _legacyIds = <String, String>{
    'briefing': 'siris.briefing',
    'homelab': 'homelab.summary',
    'running': 'running.summary',
    'gym': 'gym.summary',
    'system': 'system.summary',
    'activity': 'activity.timeline',
  };

  static final _sirisWidgets = <RegisteredMissionControlWidget>[
    RegisteredMissionControlWidget(
      definition: const MissionControlWidgetDefinition(
        id: 'siris.briefing',
        moduleId: 'siris',
        label: 'Siris briefing',
        description: 'A concise summary of what needs your attention.',
        icon: Icons.auto_awesome_rounded,
        defaultSize: MissionControlWidgetSize.wide,
      ),
      builder: (context) => DashboardHero(
        greeting: context.greeting,
        data: context.dashboard.copyWith(
          briefingItems: _briefingEngine.assemble(context.dashboard),
        ),
      ),
    ),
    RegisteredMissionControlWidget(
      definition: const MissionControlWidgetDefinition(
        id: 'siris.score',
        moduleId: 'siris',
        label: 'Siris Score',
        description: 'An explainable daily score across your active domains.',
        icon: Icons.insights_rounded,
        defaultSize: MissionControlWidgetSize.standard,
      ),
      builder: (context) => SirisScorePanel(dashboard: context.dashboard),
    ),
  ];

  static final _homelabWidgets = <RegisteredMissionControlWidget>[
    RegisteredMissionControlWidget(
      definition: const MissionControlWidgetDefinition(
        id: 'homelab.summary', moduleId: 'homelab', label: 'Homelab',
        description: 'Docker and infrastructure health at a glance.',
        icon: Icons.dns_rounded, defaultSize: MissionControlWidgetSize.standard,
      ),
      builder: (context) => SizedBox(
        height: 190,
        child: _summaryCard(context.dashboard.homelab, Icons.dns_rounded),
      ),
    ),
    RegisteredMissionControlWidget(
      definition: const MissionControlWidgetDefinition(
        id: 'homelab.prometheus', moduleId: 'homelab', label: 'Prometheus',
        description: 'Prometheus scrape target health and availability.',
        icon: Icons.monitor_heart_rounded, defaultSize: MissionControlWidgetSize.standard,
      ),
      builder: (_) => const PrometheusPanel(),
    ),
    RegisteredMissionControlWidget(
      definition: const MissionControlWidgetDefinition(
        id: 'homelab.grafana', moduleId: 'homelab', label: 'Grafana',
        description: 'Grafana availability, version and dashboard discovery.',
        icon: Icons.analytics_rounded, defaultSize: MissionControlWidgetSize.standard,
      ),
      builder: (_) => const GrafanaPanel(),
    ),
    RegisteredMissionControlWidget(
      definition: const MissionControlWidgetDefinition(
        id: 'homelab.unifi', moduleId: 'homelab', label: 'UniFi',
        description: 'UniFi controller, devices, access points, clients and WAN overview.',
        icon: Icons.wifi_rounded, defaultSize: MissionControlWidgetSize.standard,
      ),
      builder: (_) => const UniFiPanel(),
    ),
    RegisteredMissionControlWidget(
      definition: const MissionControlWidgetDefinition(
        id: 'homelab.storage', moduleId: 'homelab', label: 'Storage',
        description: 'Host filesystem capacity and low-space monitoring.',
        icon: Icons.hard_drive_rounded, defaultSize: MissionControlWidgetSize.standard,
      ),
      builder: (_) => const StoragePanel(),
    ),
    RegisteredMissionControlWidget(
      definition: const MissionControlWidgetDefinition(
        id: 'homelab.synology', moduleId: 'homelab', label: 'Synology',
        description: 'Synology DSM, disk, volume and backup capability status.',
        icon: Icons.storage_rounded, defaultSize: MissionControlWidgetSize.standard,
      ),
      builder: (_) => const SynologyPanel(),
    ),
  ];

  static final _runningWidgets = <RegisteredMissionControlWidget>[
    RegisteredMissionControlWidget(
      definition: const MissionControlWidgetDefinition(
        id: 'running.summary', moduleId: 'running', label: 'Running',
        description: 'Recent running activity and current progress.',
        icon: Icons.directions_run_rounded, defaultSize: MissionControlWidgetSize.standard,
      ),
      builder: (context) => SizedBox(
        height: 190,
        child: _summaryCard(context.dashboard.running, Icons.directions_run_rounded),
      ),
    ),
  ];

  static final _gymWidgets = <RegisteredMissionControlWidget>[
    RegisteredMissionControlWidget(
      definition: const MissionControlWidgetDefinition(
        id: 'gym.summary', moduleId: 'gym', label: 'Gym',
        description: 'Workout status and training progress.',
        icon: Icons.fitness_center_rounded, defaultSize: MissionControlWidgetSize.standard,
      ),
      builder: (context) => SizedBox(
        height: 190,
        child: _summaryCard(context.dashboard.gym, Icons.fitness_center_rounded),
      ),
    ),
  ];

  static final _systemWidgets = <RegisteredMissionControlWidget>[
    RegisteredMissionControlWidget(
      definition: const MissionControlWidgetDefinition(
        id: 'system.summary', moduleId: 'homelab', label: 'Server',
        description: 'Host CPU, memory and system status.',
        icon: Icons.memory_rounded, defaultSize: MissionControlWidgetSize.standard,
      ),
      builder: (context) => SizedBox(
        height: 190,
        child: _summaryCard(context.dashboard.system, Icons.memory_rounded),
      ),
    ),
  ];

  static final _activityWidgets = <RegisteredMissionControlWidget>[
    RegisteredMissionControlWidget(
      definition: const MissionControlWidgetDefinition(
        id: 'activity.timeline', moduleId: 'activity', label: 'Recent activity',
        description: 'A timeline of important SirisOS events.',
        icon: Icons.history_rounded, defaultSize: MissionControlWidgetSize.wide,
      ),
      builder: (_) => const ActivityFeedPanel(),
    ),
  ];

  static DashboardCard _summaryCard(DashboardCardData data, IconData icon) => DashboardCard(
        title: data.title,
        value: data.value,
        subtitle: data.subtitle,
        status: data.status,
        trend: data.trend,
        icon: icon,
      );
}
