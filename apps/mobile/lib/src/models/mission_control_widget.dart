import 'package:flutter/material.dart';

enum MissionControlWidgetSize { compact, standard, wide }

class MissionControlWidgetDefinition {
  const MissionControlWidgetDefinition({
    required this.id,
    required this.label,
    required this.description,
    required this.icon,
    required this.defaultSize,
  });

  final String id;
  final String label;
  final String description;
  final IconData icon;
  final MissionControlWidgetSize defaultSize;
}

class MissionControlWidgetRegistry {
  static const definitions = <MissionControlWidgetDefinition>[
    MissionControlWidgetDefinition(
      id: 'briefing',
      label: 'Siris briefing',
      description: 'A concise summary of what needs your attention.',
      icon: Icons.auto_awesome_rounded,
      defaultSize: MissionControlWidgetSize.wide,
    ),
    MissionControlWidgetDefinition(
      id: 'homelab',
      label: 'Homelab',
      description: 'Docker and infrastructure health at a glance.',
      icon: Icons.dns_rounded,
      defaultSize: MissionControlWidgetSize.standard,
    ),
    MissionControlWidgetDefinition(
      id: 'running',
      label: 'Running',
      description: 'Recent running activity and current progress.',
      icon: Icons.directions_run_rounded,
      defaultSize: MissionControlWidgetSize.standard,
    ),
    MissionControlWidgetDefinition(
      id: 'gym',
      label: 'Gym',
      description: 'Workout status and training progress.',
      icon: Icons.fitness_center_rounded,
      defaultSize: MissionControlWidgetSize.standard,
    ),
    MissionControlWidgetDefinition(
      id: 'system',
      label: 'Server',
      description: 'Host CPU, memory and system status.',
      icon: Icons.memory_rounded,
      defaultSize: MissionControlWidgetSize.standard,
    ),
    MissionControlWidgetDefinition(
      id: 'activity',
      label: 'Recent activity',
      description: 'A timeline of important SirisOS events.',
      icon: Icons.history_rounded,
      defaultSize: MissionControlWidgetSize.wide,
    ),
  ];

  static MissionControlWidgetDefinition definitionFor(String id) =>
      definitions.firstWhere(
        (definition) => definition.id == id,
        orElse: () => MissionControlWidgetDefinition(
          id: id,
          label: id,
          description: 'Mission Control widget',
          icon: Icons.widgets_rounded,
          defaultSize: MissionControlWidgetSize.standard,
        ),
      );
}
