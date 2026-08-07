import 'siris_event_bus.dart';

enum NotificationPolicySeverity { info, warning, critical }

enum NotificationPolicyTransition { activated, escalated, resolved }

class NotificationPolicyRule {
  const NotificationPolicyRule({
    required this.id,
    required this.moduleId,
    required this.title,
    required this.message,
    required this.severity,
    this.activeAfter = Duration.zero,
    this.escalateAfter,
    this.escalatedSeverity = NotificationPolicySeverity.critical,
    this.scorePenalty = 0,
  });

  final String id;
  final String moduleId;
  final String title;
  final String message;
  final NotificationPolicySeverity severity;
  final Duration activeAfter;
  final Duration? escalateAfter;
  final NotificationPolicySeverity escalatedSeverity;
  final int scorePenalty;
}

class NotificationPolicyOutcome {
  const NotificationPolicyOutcome({
    required this.rule,
    required this.severity,
    required this.firstMatchedAt,
    required this.activatedAt,
  });

  final NotificationPolicyRule rule;
  final NotificationPolicySeverity severity;
  final DateTime firstMatchedAt;
  final DateTime activatedAt;

  String get id => rule.id;
  String get moduleId => rule.moduleId;
  bool get isCritical => severity == NotificationPolicySeverity.critical;
}

class NotificationPolicyStateChanged extends SirisEvent {
  NotificationPolicyStateChanged({
    required this.outcome,
    required this.transition,
    super.occurredAt,
  });

  final NotificationPolicyOutcome outcome;
  final NotificationPolicyTransition transition;
}

class _PolicyState {
  _PolicyState({
    required this.moduleId,
    required this.firstMatchedAt,
  });

  final String moduleId;
  final DateTime firstMatchedAt;
  NotificationPolicyOutcome? outcome;
}

class NotificationPolicyEngine {
  NotificationPolicyEngine._();

  static final NotificationPolicyEngine instance = NotificationPolicyEngine._();

  final Map<String, _PolicyState> _states = {};

  List<NotificationPolicyOutcome> get activeOutcomes => _states.values
      .map((state) => state.outcome)
      .whereType<NotificationPolicyOutcome>()
      .toList(growable: false);

  List<NotificationPolicyOutcome> activeForModule(String moduleId) => activeOutcomes
      .where((outcome) => outcome.moduleId == moduleId)
      .toList(growable: false);

  void evaluate(
    NotificationPolicyRule rule, {
    required bool condition,
    DateTime? now,
  }) {
    final evaluatedAt = now ?? DateTime.now();

    if (!condition) {
      final previous = _states.remove(rule.id)?.outcome;
      if (previous != null) {
        _publish(previous, NotificationPolicyTransition.resolved);
      }
      return;
    }

    final state = _states.putIfAbsent(
      rule.id,
      () => _PolicyState(
        moduleId: rule.moduleId,
        firstMatchedAt: evaluatedAt,
      ),
    );
    final elapsed = evaluatedAt.difference(state.firstMatchedAt);
    if (elapsed.compareTo(rule.activeAfter) < 0) return;

    var severity = rule.severity;
    final escalateAfter = rule.escalateAfter;
    if (escalateAfter != null && elapsed.compareTo(escalateAfter) >= 0) {
      severity = rule.escalatedSeverity;
    }

    final previous = state.outcome;
    if (previous == null) {
      final outcome = NotificationPolicyOutcome(
        rule: rule,
        severity: severity,
        firstMatchedAt: state.firstMatchedAt,
        activatedAt: evaluatedAt,
      );
      state.outcome = outcome;
      _publish(outcome, NotificationPolicyTransition.activated);
      return;
    }

    if (previous.severity != severity) {
      final outcome = NotificationPolicyOutcome(
        rule: rule,
        severity: severity,
        firstMatchedAt: state.firstMatchedAt,
        activatedAt: previous.activatedAt,
      );
      state.outcome = outcome;
      _publish(outcome, NotificationPolicyTransition.escalated);
    }
  }

  void clearModule(String moduleId) {
    final ids = _states.entries
        .where((entry) => entry.value.moduleId == moduleId)
        .map((entry) => entry.key)
        .toList(growable: false);
    for (final id in ids) {
      final outcome = _states.remove(id)?.outcome;
      if (outcome != null) {
        _publish(outcome, NotificationPolicyTransition.resolved);
      }
    }
  }

  void reset() => _states.clear();

  void _publish(
    NotificationPolicyOutcome outcome,
    NotificationPolicyTransition transition,
  ) {
    SirisEventBus.instance.publish(
      NotificationPolicyStateChanged(outcome: outcome, transition: transition),
    );
    SirisEventBus.instance.publish(
      NotificationStateChanged(source: 'notification_policy'),
    );
    SirisEventBus.instance.publish(
      ModuleDataChanged(
        moduleId: outcome.moduleId,
        reason: 'notification_policy_${transition.name}',
      ),
    );
  }
}
