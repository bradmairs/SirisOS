import 'package:flutter/material.dart';

enum SirisModuleCapability {
  dashboardWidget,
  search,
  notifications,
  quickAction,
  backgroundRefresh,
}

enum SirisModuleAction {
  open,
  logRun,
  logWorkout,
}

class SirisModuleDefinition {
  const SirisModuleDefinition({
    required this.id,
    required this.label,
    required this.description,
    required this.icon,
    required this.selectedIcon,
    required this.capabilities,
    this.primaryAction = SirisModuleAction.open,
    this.primaryActionLabel,
    this.showInNavigation = true,
  });

  final String id;
  final String label;
  final String description;
  final IconData icon;
  final IconData selectedIcon;
  final Set<SirisModuleCapability> capabilities;
  final SirisModuleAction primaryAction;
  final String? primaryActionLabel;
  final bool showInNavigation;

  bool supports(SirisModuleCapability capability) =>
      capabilities.contains(capability);
}

class SirisModuleRegistry {
  SirisModuleRegistry._();

  static const modules = <SirisModuleDefinition>[
    SirisModuleDefinition(
      id: 'dashboard',
      label: 'Dashboard',
      description: 'Mission Control overview and daily priorities.',
      icon: Icons.dashboard_outlined,
      selectedIcon: Icons.dashboard_rounded,
      capabilities: {
        SirisModuleCapability.dashboardWidget,
        SirisModuleCapability.search,
        SirisModuleCapability.backgroundRefresh,
      },
    ),
    SirisModuleDefinition(
      id: 'homelab',
      label: 'Homelab',
      description: 'Docker, host metrics, alerts and infrastructure integrations.',
      icon: Icons.dns_outlined,
      selectedIcon: Icons.dns_rounded,
      capabilities: {
        SirisModuleCapability.dashboardWidget,
        SirisModuleCapability.search,
        SirisModuleCapability.notifications,
        SirisModuleCapability.quickAction,
        SirisModuleCapability.backgroundRefresh,
      },
      primaryActionLabel: 'Open Homelab',
    ),
    SirisModuleDefinition(
      id: 'running',
      label: 'Running',
      description: 'Runs, fitness trends and training progress.',
      icon: Icons.directions_run_outlined,
      selectedIcon: Icons.directions_run_rounded,
      capabilities: {
        SirisModuleCapability.dashboardWidget,
        SirisModuleCapability.search,
        SirisModuleCapability.quickAction,
        SirisModuleCapability.backgroundRefresh,
      },
      primaryAction: SirisModuleAction.logRun,
      primaryActionLabel: 'Log a run',
    ),
    SirisModuleDefinition(
      id: 'gym',
      label: 'Gym',
      description: 'Workouts, templates, exercise progress and personal records.',
      icon: Icons.fitness_center_outlined,
      selectedIcon: Icons.fitness_center_rounded,
      capabilities: {
        SirisModuleCapability.dashboardWidget,
        SirisModuleCapability.search,
        SirisModuleCapability.quickAction,
        SirisModuleCapability.backgroundRefresh,
      },
      primaryAction: SirisModuleAction.logWorkout,
      primaryActionLabel: 'Log a workout',
    ),
    SirisModuleDefinition(
      id: 'health',
      label: 'Health',
      description: 'Health snapshots, recovery and imported Apple Health data.',
      icon: Icons.favorite_outline_rounded,
      selectedIcon: Icons.favorite_rounded,
      capabilities: {
        SirisModuleCapability.search,
        SirisModuleCapability.quickAction,
        SirisModuleCapability.backgroundRefresh,
      },
      primaryActionLabel: 'Open Health',
    ),
    SirisModuleDefinition(
      id: 'engineering',
      label: 'Engineering',
      description: 'Civil engineering calculators, standards and project tools.',
      icon: Icons.engineering_outlined,
      selectedIcon: Icons.engineering_rounded,
      capabilities: {
        SirisModuleCapability.search,
        SirisModuleCapability.quickAction,
      },
      primaryActionLabel: 'Open Engineering',
    ),
    SirisModuleDefinition(
      id: 'knowledge',
      label: 'Knowledge',
      description: 'Browse and search your private Markdown/Obsidian vault.',
      icon: Icons.menu_book_outlined,
      selectedIcon: Icons.menu_book_rounded,
      capabilities: {
        SirisModuleCapability.search,
        SirisModuleCapability.quickAction,
        SirisModuleCapability.backgroundRefresh,
      },
      primaryActionLabel: 'Open Knowledge',
    ),
    SirisModuleDefinition(
      id: 'projects',
      label: 'Projects',
      description: 'Context containers linking Knowledge and future SirisOS work objects.',
      icon: Icons.folder_outlined,
      selectedIcon: Icons.folder_rounded,
      capabilities: {
        SirisModuleCapability.quickAction,
      },
      primaryActionLabel: 'Open Projects',
    ),
    SirisModuleDefinition(
      id: 'siris',
      label: 'Siris',
      description: 'AI context, recommendations and personal knowledge tools.',
      icon: Icons.auto_awesome_outlined,
      selectedIcon: Icons.auto_awesome_rounded,
      capabilities: {
        SirisModuleCapability.search,
        SirisModuleCapability.notifications,
      },
    ),
  ];

  static List<SirisModuleDefinition> get navigationModules => modules
      .where((module) => module.showInNavigation)
      .toList(growable: false);

  static SirisModuleDefinition? find(String id) {
    for (final module in modules) {
      if (module.id == id) return module;
    }
    return null;
  }

  static int navigationIndexOf(String id) =>
      navigationModules.indexWhere((module) => module.id == id);

  static Iterable<SirisModuleDefinition> supporting(
    SirisModuleCapability capability,
  ) => modules.where((module) => module.supports(capability));
}
