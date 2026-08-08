import 'dart:async';

import 'notification_policy.dart';
import 'siris_connector.dart';
import 'siris_event_bus.dart';
import 'siris_integration_manager.dart';

enum SirisContextDomain { personal, homelab, engineering, ai }

class SirisContextFact {
  const SirisContextFact({
    required this.id,
    required this.label,
    required this.domain,
    required this.priority,
    required this.source,
    this.detail,
    this.active = true,
    this.observedAt,
  });

  final String id;
  final String label;
  final SirisContextDomain domain;
  final int priority;
  final String source;
  final String? detail;
  final bool active;
  final DateTime? observedAt;

  SirisContextFact copyWith({DateTime? observedAt}) => SirisContextFact(
        id: id,
        label: label,
        domain: domain,
        priority: priority,
        source: source,
        detail: detail,
        active: active,
        observedAt: observedAt ?? this.observedAt,
      );
}

abstract class SirisContextProvider {
  String get id;
  Future<List<SirisContextFact>> collect();
}

class SirisContextSnapshot {
  const SirisContextSnapshot({
    required this.generatedAt,
    required this.facts,
  });

  final DateTime generatedAt;
  final List<SirisContextFact> facts;

  SirisContextFact? get primary => facts.isEmpty ? null : facts.first;

  List<SirisContextFact> forDomain(SirisContextDomain domain) =>
      facts.where((fact) => fact.domain == domain).toList(growable: false);
}

class SirisContextTimelineEntry {
  const SirisContextTimelineEntry({
    required this.occurredAt,
    required this.factId,
    required this.label,
    required this.active,
    required this.source,
  });

  final DateTime occurredAt;
  final String factId;
  final String label;
  final bool active;
  final String source;
}

class ContextSnapshotChanged extends SirisEvent {
  ContextSnapshotChanged({required this.snapshot, super.occurredAt});

  final SirisContextSnapshot snapshot;
}

class SirisCoreContextService {
  SirisCoreContextService._();

  static final SirisCoreContextService instance = SirisCoreContextService._();

  final Map<String, SirisContextProvider> _providers = {};
  final List<SirisContextTimelineEntry> _timeline = [];
  StreamSubscription<SirisEvent>? _events;
  bool _initialized = false;
  bool _refreshing = false;

  SirisContextSnapshot _snapshot = SirisContextSnapshot(
    generatedAt: DateTime.fromMillisecondsSinceEpoch(0),
    facts: const [],
  );

  SirisContextSnapshot get snapshot => _snapshot;
  List<SirisContextTimelineEntry> get timeline =>
      List.unmodifiable(_timeline.reversed.take(100));

  Future<void> initializeDefaults() async {
    if (_initialized) return;
    _initialized = true;
    register(const _OperationalContextProvider());
    _events = SirisEventBus.instance.events.listen((event) {
      if (event is IntegrationHealthChanged ||
          event is NotificationPolicyStateChanged) {
        unawaited(refresh());
      }
    });
    await refresh();
  }

  void register(SirisContextProvider provider) {
    _providers[provider.id] = provider;
  }

  void unregister(String providerId) {
    _providers.remove(providerId);
  }

  Future<void> refresh() async {
    if (_refreshing) return;
    _refreshing = true;
    try {
      final now = DateTime.now();
      final nextFacts = <SirisContextFact>[];
      for (final provider in _providers.values) {
        try {
          final facts = await provider.collect();
          nextFacts.addAll(
            facts.where((fact) => fact.active).map((fact) => fact.copyWith(
                  observedAt: fact.observedAt ?? now,
                )),
          );
        } catch (_) {
          // Context providers are enrichment only and must never break the shell.
        }
      }
      nextFacts.sort((a, b) {
        final priority = b.priority.compareTo(a.priority);
        if (priority != 0) return priority;
        return a.label.compareTo(b.label);
      });

      _recordTransitions(_snapshot.facts, nextFacts, now);
      _snapshot = SirisContextSnapshot(generatedAt: now, facts: nextFacts);
      SirisEventBus.instance.publish(ContextSnapshotChanged(snapshot: _snapshot));
    } finally {
      _refreshing = false;
    }
  }

  Future<void> dispose() async {
    await _events?.cancel();
    _events = null;
    _initialized = false;
  }

  void _recordTransitions(
    List<SirisContextFact> previous,
    List<SirisContextFact> next,
    DateTime now,
  ) {
    final before = {for (final fact in previous) fact.id: fact};
    final after = {for (final fact in next) fact.id: fact};

    for (final entry in after.entries) {
      if (!before.containsKey(entry.key)) {
        _timeline.add(
          SirisContextTimelineEntry(
            occurredAt: now,
            factId: entry.key,
            label: entry.value.label,
            active: true,
            source: entry.value.source,
          ),
        );
      }
    }
    for (final entry in before.entries) {
      if (!after.containsKey(entry.key)) {
        _timeline.add(
          SirisContextTimelineEntry(
            occurredAt: now,
            factId: entry.key,
            label: entry.value.label,
            active: false,
            source: entry.value.source,
          ),
        );
      }
    }

    if (_timeline.length > 200) {
      _timeline.removeRange(0, _timeline.length - 200);
    }
  }
}

class _OperationalContextProvider implements SirisContextProvider {
  const _OperationalContextProvider();

  @override
  String get id => 'core.operational';

  @override
  Future<List<SirisContextFact>> collect() async {
    final facts = <SirisContextFact>[];
    final outcomes = NotificationPolicyEngine.instance.activeOutcomes;
    final health = SirisIntegrationManager.instance.health;

    final onBattery = outcomes.any(
      (item) => item.id == 'ups.on_battery' || item.id == 'ups.low_battery',
    );
    if (onBattery) {
      facts.add(
        const SirisContextFact(
          id: 'homelab.power_event',
          label: 'Power event',
          domain: SirisContextDomain.homelab,
          priority: 100,
          source: 'ups',
          detail: 'UPS power-state policy is active.',
        ),
      );
    }

    if (outcomes.any((item) => item.id.startsWith('synology.hyper_backup.'))) {
      facts.add(
        const SirisContextFact(
          id: 'homelab.backup_attention',
          label: 'Backup attention',
          domain: SirisContextDomain.homelab,
          priority: 80,
          source: 'synology',
          detail: 'Hyper Backup requires attention.',
        ),
      );
    }

    final degradedNetwork = ['unifi']
        .any((id) => health[id]?.hasError ?? false);
    if (degradedNetwork) {
      facts.add(
        const SirisContextFact(
          id: 'homelab.network_degraded',
          label: 'Network degraded',
          domain: SirisContextDomain.homelab,
          priority: 75,
          source: 'unifi',
        ),
      );
    }

    final degradedStorage = ['synology', 'storage']
        .any((id) => health[id]?.hasError ?? false);
    if (degradedStorage) {
      facts.add(
        const SirisContextFact(
          id: 'homelab.storage_degraded',
          label: 'Storage degraded',
          domain: SirisContextDomain.homelab,
          priority: 70,
          source: 'storage',
        ),
      );
    }

    final degradedCompute = ['docker']
        .any((id) => health[id]?.hasError ?? false);
    if (degradedCompute) {
      facts.add(
        const SirisContextFact(
          id: 'homelab.compute_degraded',
          label: 'Compute degraded',
          domain: SirisContextDomain.homelab,
          priority: 70,
          source: 'docker',
        ),
      );
    }

    if (facts.isEmpty) {
      facts.add(
        const SirisContextFact(
          id: 'homelab.nominal',
          label: 'Homelab nominal',
          domain: SirisContextDomain.homelab,
          priority: 10,
          source: 'core',
          detail: 'No elevated operational context is active.',
        ),
      );
    }

    return facts;
  }
}
