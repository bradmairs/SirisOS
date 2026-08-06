import 'package:flutter/material.dart';

enum SirisModuleCapability {
  dashboardWidget,
  search,
  notifications,
  quickAction,
  backgroundRefresh,
}

class SirisModuleDefinition {
  const SirisModuleDefinition({
    required this.id,
    required this.label,
    required this.description,
    required this.icon,
    required this.capabilities,
  });

  final String id;
  final String label;
  final String description;
  final IconData icon;
  final Set<SirisModuleCapability> capabilities;

  bool supports(SirisModuleCapability capability) => capabilities.contains(capability);
}

class SirisModuleRegistry {
  SirisModuleRegistry._();

  static const modules = <SirisModuleDefinition>[
    SirisModuleDefinition(
      id: 'homelab',
      label: 'Homelab',
      description: 'Docker, host metrics, alerts and infrastructure integrations.',
      icon: Icons.dns_rounded,
      capabilities: {
        SirisModuleCapability.dashboardWidget,
        SirisModuleCapability.search,
        SirisModuleCapability.notifications,
        SirisModuleCapability.quickAction,
        SirisModuleCapability.backgroundRefresh,
      },
    ),
    SirisModuleDefinition(
      id: 'running',
      label: 'Running',
      description: 'Runs, fitness trends and training progress.',
      icon: Icons.directions_run_rounded,
      capabilities: {
        SirisModuleCapability.dashboardWidget,
        SirisModuleCapability.search,
        SirisModuleCapability.quickAction,
        SirisModuleCapability.backgroundRefresh,
      },
    ),
    SirisModuleDefinition(
      id: 'gym',
      label: 'Gym',
      description: 'Workouts, templates, exercise progress and personal records.',
      icon: Icons.fitness_center_rounded,
      capabilities: {
        SirisModuleCapability.dashboardWidget,
        SirisModuleCapability.search,
        SirisModuleCapability.quickAction,
        SirisModuleCapability.backgroundRefresh,
      },
    ),
    SirisModuleDefinition(
      id: 'health',
      label: 'Health',
      description: 'Health snapshots, recovery and imported Apple Health data.',
      icon: Icons.favorite_rounded,
      capabilities: {
        SirisModuleCapability.search,
        SirisModuleCapability.quickAction,
        SirisModuleCapability.backgroundRefresh,
      },
    ),
    SirisModuleDefinition(
      id: 'siris',
      label: 'Siris',
      description: 'AI context, recommendations and personal knowledge tools.',
      icon: Icons.auto_awesome_rounded,
      capabilities: {
        SirisModuleCapability.search,
        SirisModuleCapability.notifications,
      },
    ),
  ];

  static SirisModuleDefinition? find(String id) {
    for (final module in modules) {
      if (module.id == id) return module;
    }
    return null;
  }

  static Iterable<SirisModuleDefinition> supporting(
    SirisModuleCapability capability,
  ) => modules.where((module) => module.supports(capability));
}
