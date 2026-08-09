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

    test('part-full circular Manning handles half-full geometry', () {
      final result = EngineeringCalculators.partFullCircularPipe(
        diameterM: 0.60,
        depthM: 0.30,
        roughnessN: 0.013,
        slope: 0.005,
      );
      expect(result.areaM2, closeTo(0.14137, 0.0001));
      expect(result.flowM3s, closeTo(0.21709, 0.0001));
      expect(result.velocityMs, closeTo(1.5356, 0.001));
    });

    test('minimum pipe grade inverts full-flow Manning correctly', () {
      final result = EngineeringCalculators.minimumCircularPipeGrade(
        diameterM: 0.45,
        roughnessN: 0.013,
        targetFlowM3s: 0.20,
      );
      expect(result.slope, closeTo(0.004921, 0.000001));
      expect(result.gradePercent, closeTo(0.4921, 0.0001));
    });

    test('rectangular channel Manning returns expected flow', () {
      final result = EngineeringCalculators.rectangularChannel(
        widthM: 1.0,
        depthM: 0.30,
        roughnessN: 0.015,
        slope: 0.005,
      );
      expect(result.flowM3s, closeTo(0.46329, 0.0001));
      expect(result.velocityMs, closeTo(1.5443, 0.001));
    });

    test('rectangular critical depth returns expected depth', () {
      final result = EngineeringCalculators.rectangularCriticalDepth(
        flowM3s: 0.50,
        widthM: 1.0,
      );
      expect(result.depthM, closeTo(0.29431, 0.0001));
      expect(result.velocityMs, closeTo(1.6989, 0.001));
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

    test('rectangular weir returns expected free discharge', () {
      final result = EngineeringCalculators.rectangularWeir(
        dischargeCoefficient: 0.62,
        widthM: 1.0,
        headM: 0.30,
      );
      expect(result.flowM3s, closeTo(0.30079, 0.0001));
    });

    test('circular orifice returns flow and velocity', () {
      final result = EngineeringCalculators.circularOrifice(
        dischargeCoefficient: 0.62,
        diameterM: 0.15,
        headM: 1.0,
      );
      expect(result.flowM3s, closeTo(0.04852, 0.0001));
      expect(result.velocityMs!, closeTo(2.7458, 0.001));
    });

    test('Hazen-Williams returns expected headloss', () {
      final result = EngineeringCalculators.hazenWilliams(
        flowM3s: 0.05,
        diameterM: 0.20,
        lengthM: 100,
        coefficientC: 140,
      );
      expect(result.headlossM, closeTo(1.1169, 0.001));
      expect(result.velocityMs, closeTo(1.5915, 0.001));
    });

    test('Darcy-Weisbach returns turbulent friction result', () {
      final result = EngineeringCalculators.darcyWeisbach(
        flowM3s: 0.05,
        diameterM: 0.20,
        lengthM: 100,
        absoluteRoughnessMm: 0.045,
      );
      expect(result.reynoldsNumber!, closeTo(317042, 5));
      expect(result.frictionFactor!, closeTo(0.01641, 0.0001));
      expect(result.headlossM, closeTo(1.0598, 0.001));
    });

    test('minor loss sums K values into headloss', () {
      final result = EngineeringCalculators.minorLoss(
        flowM3s: 0.05,
        diameterM: 0.20,
        sumKValues: 1.5,
      );
      expect(result.velocityMs, closeTo(1.5915, 0.001));
      expect(result.headlossM, closeTo(0.19372, 0.0005));
    });

    test('minor loss rejects a negative K value', () {
      expect(
        () => EngineeringCalculators.minorLoss(
          flowM3s: 0.05,
          diameterM: 0.20,
          sumKValues: -0.5,
        ),
        throwsArgumentError,
      );
    });

    test('pump power accounts for efficiency', () {
      final result = EngineeringCalculators.pumpPower(
        flowM3s: 0.05,
        totalHeadM: 20,
        efficiencyPercent: 75,
      );
      expect(result.hydraulicPowerKw, closeTo(9.80665, 0.001));
      expect(result.inputPowerKw, closeTo(13.0755, 0.001));
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
        () => EngineeringCalculators.partFullCircularPipe(
          diameterM: 0.45,
          depthM: 0.55,
          roughnessN: 0.013,
          slope: 0.005,
        ),
        throwsArgumentError,
      );
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
