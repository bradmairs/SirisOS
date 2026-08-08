import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/core/capability_registry.dart';
import 'package:siris_os/src/core/siris_connector.dart';

void main() {
  final registry = SirisCapabilityRegistry.instance;

  test('healthy provider exposes control capability', () {
    final status = registry.statusFor(
      'docker.restart',
      health: const {
        'docker': SirisConnectorHealth(
          state: SirisConnectorState.healthy,
          message: 'Healthy',
        ),
      },
    );

    expect(status.available, isTrue);
    expect(status.capability.requiresConfirmation, isTrue);
  });

  test('degraded provider keeps read capability but fails control closed', () {
    const health = {
      'docker': SirisConnectorHealth(
        state: SirisConnectorState.degraded,
        message: 'Degraded',
      ),
    };

    expect(registry.statusFor('docker.observe', health: health).available, isTrue);
    expect(registry.statusFor('docker.restart', health: health).available, isFalse);
  });

  test('disabled provider makes capability unavailable', () {
    final status = registry.statusFor(
      'ups.observe',
      health: const {
        'ups': SirisConnectorHealth(
          state: SirisConnectorState.disabled,
          message: 'Not configured',
        ),
      },
    );

    expect(status.available, isFalse);
    expect(status.reason, contains('disabled'));
  });
}
