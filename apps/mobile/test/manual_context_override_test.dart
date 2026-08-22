import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:siris_os/src/core/manual_context_override.dart';
import 'package:siris_os/src/core/siris_context_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('set then current round-trips label, domain and detail', () async {
    final service = ManualContextOverrideService();
    await service.set(
      label: 'Focused',
      domain: SirisContextDomain.personal,
      detail: 'Deep work block',
    );

    final override = await service.current();
    expect(override, isNotNull);
    expect(override!.label, 'Focused');
    expect(override.domain, SirisContextDomain.personal);
    expect(override.detail, 'Deep work block');
    expect(override.expiresAt, isNull);
  });

  test('current returns null once the expiry has passed, and clears it from storage', () async {
    final service = ManualContextOverrideService();
    await service.set(
      label: 'Away from home',
      domain: SirisContextDomain.personal,
      expiresIn: const Duration(milliseconds: -1),
    );

    expect(await service.current(), isNull);
    // A second read confirms the expired entry was actually removed, not
    // just filtered on this one read.
    expect(await service.current(), isNull);
  });

  test('clear removes the override immediately', () async {
    final service = ManualContextOverrideService();
    await service.set(label: 'Travelling', domain: SirisContextDomain.personal);
    expect(await service.current(), isNotNull);

    await service.clear();
    expect(await service.current(), isNull);
  });

  test('current returns null when nothing has ever been set', () async {
    final service = ManualContextOverrideService();
    expect(await service.current(), isNull);
  });

  test('provider yields no facts when no override is active', () async {
    final provider = ManualContextOverrideProvider(service: ManualContextOverrideService());
    expect(await provider.collect(), isEmpty);
  });

  test('provider yields a high-priority manual fact when an override is active', () async {
    final service = ManualContextOverrideService();
    await service.set(
      label: 'Focused',
      domain: SirisContextDomain.engineering,
      detail: 'Client deadline',
      expiresIn: const Duration(hours: 1),
    );

    final provider = ManualContextOverrideProvider(service: service);
    final facts = await provider.collect();

    expect(facts, hasLength(1));
    expect(facts.single.id, 'manual.override');
    expect(facts.single.label, 'Focused');
    expect(facts.single.domain, SirisContextDomain.engineering);
    expect(facts.single.source, 'manual');
    expect(facts.single.detail, 'Client deadline');
    // Higher than every existing provider-derived priority (the highest,
    // UPS power events, is 100), so a manual assertion always wins as primary.
    expect(facts.single.priority, greaterThan(100));
  });
}
