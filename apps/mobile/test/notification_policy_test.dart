import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/core/notification_policy.dart';

void main() {
  final engine = NotificationPolicyEngine.instance;

  setUp(engine.reset);
  tearDown(engine.reset);

  test('policy activates only after its duration threshold', () {
    const rule = NotificationPolicyRule(
      id: 'test.duration',
      moduleId: 'homelab',
      title: 'Duration test',
      message: 'Condition persisted.',
      severity: NotificationPolicySeverity.warning,
      activeAfter: Duration(minutes: 5),
    );
    final started = DateTime(2026, 8, 7, 12);

    engine.evaluate(rule, condition: true, now: started);
    engine.evaluate(
      rule,
      condition: true,
      now: started.add(const Duration(minutes: 4, seconds: 59)),
    );
    expect(engine.activeOutcomes, isEmpty);

    engine.evaluate(
      rule,
      condition: true,
      now: started.add(const Duration(minutes: 5)),
    );
    expect(engine.activeOutcomes, hasLength(1));
    expect(
      engine.activeOutcomes.single.severity,
      NotificationPolicySeverity.warning,
    );
  });

  test('policy escalates without creating a duplicate outcome', () {
    const rule = NotificationPolicyRule(
      id: 'test.escalation',
      moduleId: 'homelab',
      title: 'Escalation test',
      message: 'Condition persisted.',
      severity: NotificationPolicySeverity.warning,
      activeAfter: Duration(minutes: 2),
      escalateAfter: Duration(minutes: 5),
      escalatedSeverity: NotificationPolicySeverity.critical,
    );
    final started = DateTime(2026, 8, 7, 12);

    engine.evaluate(rule, condition: true, now: started);
    engine.evaluate(
      rule,
      condition: true,
      now: started.add(const Duration(minutes: 2)),
    );
    engine.evaluate(
      rule,
      condition: true,
      now: started.add(const Duration(minutes: 5)),
    );

    expect(engine.activeOutcomes, hasLength(1));
    expect(
      engine.activeOutcomes.single.severity,
      NotificationPolicySeverity.critical,
    );
  });

  test('policy resolves when the condition clears', () {
    const rule = NotificationPolicyRule(
      id: 'test.resolve',
      moduleId: 'homelab',
      title: 'Resolution test',
      message: 'Condition active.',
      severity: NotificationPolicySeverity.warning,
    );
    final now = DateTime(2026, 8, 7, 12);

    engine.evaluate(rule, condition: true, now: now);
    expect(engine.activeOutcomes, hasLength(1));

    engine.evaluate(
      rule,
      condition: false,
      now: now.add(const Duration(minutes: 1)),
    );
    expect(engine.activeOutcomes, isEmpty);
  });
}
