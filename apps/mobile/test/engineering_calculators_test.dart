import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/core/engineering_calculators.dart';

void main() {
  group('EngineeringCalculators', () {
    test('full circular Manning calculation returns expected capacity', () {
      final result = EngineeringCalculators.fullCircularPipe(
        diameterM: 0.45,
        roughnessN: 0.013,
        slope: 0.005,
      );

      expect(result.flowM3s, closeTo(0.20160, 0.0001));
      expect(result.velocityMs, closeTo(1.2676, 0.001));
    });

    test('Rational Method uses Australian civil units correctly', () {
      final result = EngineeringCalculators.rationalMethod(
        runoffCoefficient: 0.8,
        intensityMmHr: 100,
        areaHa: 1.0,
      );

      expect(result.flowM3s, closeTo(0.22222, 0.0001));
      expect(result.flowLs, closeTo(222.22, 0.1));
    });

    test('constant-flow detention stores excess flow over duration', () {
      final result = EngineeringCalculators.constantFlowDetention(
        inflowM3s: 0.2,
        allowableOutflowM3s: 0.1,
        durationMinutes: 30,
      );

      expect(result.storageM3, closeTo(180, 0.001));
    });

    test('buoyancy check returns finite resistance and factor of safety', () {
      final result = EngineeringCalculators.pipeBuoyancy(
        outsideDiameterM: 0.55,
        insideDiameterM: 0.45,
        lengthM: 1,
        pipeDensityKgM3: 2400,
        soilCoverM: 0.75,
        submergedSoilUnitWeightKnM3: 10,
      );

      expect(result.buoyantForceKn, greaterThan(0));
      expect(result.resistingForceKn, greaterThan(0));
      expect(result.factorOfSafety.isFinite, isTrue);
    });

    test('invalid geometry is rejected', () {
      expect(
        () => EngineeringCalculators.pipeBuoyancy(
          outsideDiameterM: 0.45,
          insideDiameterM: 0.55,
          lengthM: 1,
          pipeDensityKgM3: 2400,
          soilCoverM: 0.75,
          submergedSoilUnitWeightKnM3: 10,
        ),
        throwsArgumentError,
      );
    });
  });
}
