import 'package:flutter/material.dart';

import '../core/module_registry.dart';
import '../screens/dashboard_screen.dart';
import '../screens/engineering_hub_screen.dart';
import '../screens/gym_screen.dart';
import '../screens/health_screen.dart';
import '../screens/homelab_screen.dart';
import '../screens/knowledge_hub_screen.dart';
import '../screens/running_screen.dart';
import '../widgets/siris_logo.dart';

enum SirisModuleAvailability { available, preview, unavailable }

class SirisModuleScreenContext {
  const SirisModuleScreenContext({
    required this.runAddRequest,
    required this.workoutAddRequest,
  });

  final int runAddRequest;
  final int workoutAddRequest;
}

typedef SirisModuleScreenBuilder = Widget Function(
  SirisModuleScreenContext context,
);

class SirisModuleRegistration {
  const SirisModuleRegistration({
    required this.definition,
    required this.screenBuilder,
    this.availability = SirisModuleAvailability.available,
    this.unavailableReason,
  });

  final SirisModuleDefinition definition;
  final SirisModuleScreenBuilder screenBuilder;
  final SirisModuleAvailability availability;
  final String? unavailableReason;

  bool get isAvailable => availability == SirisModuleAvailability.available;

  Widget buildScreen(SirisModuleScreenContext context) {
    if (availability == SirisModuleAvailability.available) {
      return screenBuilder(context);
    }
    return _ModuleAvailabilityScreen(
      module: definition,
      availability: availability,
      reason: unavailableReason,
    );
  }
}

class AppModuleRegistry {
  AppModuleRegistry._();

  static final List<SirisModuleRegistration> registrations =
      SirisModuleRegistry.navigationModules.map(_registrationFor).toList(
            growable: false,
          );

  static SirisModuleRegistration? find(String moduleId) {
    for (final registration in registrations) {
      if (registration.definition.id == moduleId) return registration;
    }
    return null;
  }

  static int navigationIndexOf(String moduleId) => registrations.indexWhere(
        (registration) => registration.definition.id == moduleId,
      );

  static SirisModuleRegistration _registrationFor(
    SirisModuleDefinition definition,
  ) => switch (definition.id) {
        'dashboard' => SirisModuleRegistration(
            definition: definition,
            screenBuilder: (_) => const DashboardScreen(),
          ),
        'homelab' => SirisModuleRegistration(
            definition: definition,
            screenBuilder: (_) => const HomelabScreen(),
          ),
        'running' => SirisModuleRegistration(
            definition: definition,
            screenBuilder: (context) => RunningScreen(
              addRequest: context.runAddRequest,
            ),
          ),
        'gym' => SirisModuleRegistration(
            definition: definition,
            screenBuilder: (context) => GymScreen(
              addRequest: context.workoutAddRequest,
            ),
          ),
        'health' => SirisModuleRegistration(
            definition: definition,
            screenBuilder: (_) => const HealthScreen(),
          ),
        'engineering' => SirisModuleRegistration(
            definition: definition,
            screenBuilder: (_) => const EngineeringHubScreen(),
          ),
        'knowledge' => SirisModuleRegistration(
            definition: definition,
            screenBuilder: (_) => const KnowledgeHubScreen(),
          ),
        'siris' => SirisModuleRegistration(
            definition: definition,
            availability: SirisModuleAvailability.preview,
            unavailableReason:
                'The Siris AI command centre is planned for a later sprint.',
            screenBuilder: (_) => const SizedBox.shrink(),
          ),
        _ => SirisModuleRegistration(
            definition: definition,
            availability: SirisModuleAvailability.unavailable,
            unavailableReason: 'This module has not been connected yet.',
            screenBuilder: (_) => const SizedBox.shrink(),
          ),
      };
}

class _ModuleAvailabilityScreen extends StatelessWidget {
  const _ModuleAvailabilityScreen({
    required this.module,
    required this.availability,
    this.reason,
  });

  final SirisModuleDefinition module;
  final SirisModuleAvailability availability;
  final String? reason;

  @override
  Widget build(BuildContext context) {
    final preview = availability == SirisModuleAvailability.preview;
    return SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (module.id == 'siris')
                const SirisLogo(size: 82)
              else
                Icon(module.selectedIcon, size: 64),
              const SizedBox(height: 22),
              Text(
                module.label,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                preview ? 'Preview module' : 'Module unavailable',
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: Theme.of(context).colorScheme.primary,
                    ),
              ),
              const SizedBox(height: 10),
              Text(
                reason ?? module.description,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
