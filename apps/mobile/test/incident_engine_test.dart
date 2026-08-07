import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/core/incident_engine.dart';
import 'package:siris_os/src/core/notification_policy.dart';

NotificationPolicyOutcome outcome(
  String id, {
  NotificationPolicySeverity severity = NotificationPolicySeverity.warning,
  DateTime? activatedAt,
}) {
  final at = activatedAt ?? DateTime(2026, 8, 8, 8);
  return NotificationPolicyOutcome(
    rule: NotificationPolicyRule(
      id: id,
      moduleId: 'homelab',
      title: id,
      message: '$id message',
      severity: severity,
    ),
    severity: severity,
    firstMatchedAt: at,
    activatedAt: at,
  );
}

void main() {
  test('UPS outage anchors related infrastructure conditions', () {
    final incidents = IncidentEngine.instance.correlate(
      outcomes: [
        outcome('ups.on_battery'),
        outcome('docker.stopped'),
        outcome('synology.unavailable', severity: NotificationPolicySeverity.critical),
      ],
      integrationHealth: const {},
    );

    expect(incidents, hasLength(1));
    expect(incidents.single.id, 'incident.power');
    expect(incidents.single.title, 'Power outage');
    expect(incidents.single.severity, SirisIncidentSeverity.critical);
    expect(incidents.single.policyOutcomes, hasLength(3));
    expect(incidents.single.affectedIntegrations, containsAll(['UPS', 'Docker', 'Synology']));
  });

  test('related Docker policies become one compute incident', () {
    final incidents = IncidentEngine.instance.correlate(
      outcomes: [outcome('docker.unhealthy'), outcome('docker.stopped')],
      integrationHealth: const {},
    );

    expect(incidents, hasLength(1));
    expect(incidents.single.id, 'incident.compute');
    expect(incidents.single.policyOutcomes, hasLength(2));
  });

  test('unmatched policies remain visible as standalone incidents', () {
    final incidents = IncidentEngine.instance.correlate(
      outcomes: [outcome('custom.rule')],
      integrationHealth: const {},
    );

    expect(incidents, hasLength(1));
    expect(incidents.single.id, 'incident.policy.custom.rule');
    expect(incidents.single.correlationReason, contains('Standalone'));
  });
}
