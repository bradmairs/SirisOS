import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/core/siris_context_service.dart';

class _StaticProvider implements SirisContextProvider {
  const _StaticProvider(this.id, this.facts);

  @override
  final String id;
  final List<SirisContextFact> facts;

  @override
  Future<List<SirisContextFact>> collect() async => facts;
}

void main() {
  final service = SirisCoreContextService.instance;

  tearDown(() {
    service.unregister('test.low');
    service.unregister('test.high');
  });

  test('highest priority context becomes primary', () async {
    service.register(
      const _StaticProvider('test.low', [
        SirisContextFact(
          id: 'personal.home',
          label: 'Home',
          domain: SirisContextDomain.personal,
          priority: 20,
          source: 'test',
        ),
      ]),
    );
    service.register(
      const _StaticProvider('test.high', [
        SirisContextFact(
          id: 'homelab.power_event',
          label: 'Power event',
          domain: SirisContextDomain.homelab,
          priority: 100,
          source: 'test',
        ),
      ]),
    );

    await service.refresh();

    expect(service.snapshot.primary?.id, 'homelab.power_event');
    expect(service.snapshot.facts.map((item) => item.id).toList(), [
      'homelab.power_event',
      'personal.home',
    ]);
  });

  test('refresh records context enter and clear transitions', () async {
    service.register(
      const _StaticProvider('test.high', [
        SirisContextFact(
          id: 'engineering.design_mode',
          label: 'Design mode',
          domain: SirisContextDomain.engineering,
          priority: 60,
          source: 'test',
        ),
      ]),
    );
    await service.refresh();

    service.unregister('test.high');
    await service.refresh();

    final recent = service.timeline.where(
      (item) => item.factId == 'engineering.design_mode',
    );
    expect(recent.any((item) => item.active), isTrue);
    expect(recent.any((item) => !item.active), isTrue);
  });
}
