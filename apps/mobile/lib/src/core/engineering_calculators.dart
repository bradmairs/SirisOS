import 'dart:math' as math;

class ManningResult {
  const ManningResult({
    required this.flowM3s,
    required this.velocityMs,
    required this.areaM2,
    required this.hydraulicRadiusM,
  });

  final double flowM3s;
  final double velocityMs;
  final double areaM2;
  final double hydraulicRadiusM;
}

class RationalMethodResult {
  const RationalMethodResult({required this.flowM3s});

  final double flowM3s;
  double get flowLs => flowM3s * 1000;
}

class PipeBuoyancyResult {
  const PipeBuoyancyResult({
    required this.buoyantForceKn,
    required this.pipeWeightKn,
    required this.soilWeightKn,
    required this.resistingForceKn,
    required this.factorOfSafety,
  });

  final double buoyantForceKn;
  final double pipeWeightKn;
  final double soilWeightKn;
  final double resistingForceKn;
  final double factorOfSafety;

  bool get stable => factorOfSafety >= 1.0;
}

class DetentionResult {
  const DetentionResult({
    required this.inflowM3s,
    required this.outflowM3s,
    required this.storageM3,
  });

  final double inflowM3s;
  final double outflowM3s;
  final double storageM3;
}

class EngineeringCalculators {
  const EngineeringCalculators._();

  static ManningResult fullCircularPipe({
    required double diameterM,
    required double roughnessN,
    required double slope,
  }) {
    _positive(diameterM, 'diameter');
    _positive(roughnessN, 'roughness');
    _positive(slope, 'slope');

    final area = math.pi * diameterM * diameterM / 4;
    final hydraulicRadius = diameterM / 4;
    final radiusTerm = math.pow(hydraulicRadius, 2 / 3).toDouble();
    final flow =
        (1 / roughnessN) * area * radiusTerm * math.sqrt(slope);
    return ManningResult(
      flowM3s: flow,
      velocityMs: flow / area,
      areaM2: area,
      hydraulicRadiusM: hydraulicRadius,
    );
  }

  static RationalMethodResult rationalMethod({
    required double runoffCoefficient,
    required double intensityMmHr,
    required double areaHa,
  }) {
    if (runoffCoefficient < 0 || runoffCoefficient > 1) {
      throw ArgumentError('runoffCoefficient must be between 0 and 1');
    }
    _positive(intensityMmHr, 'intensity');
    _positive(areaHa, 'area');
    return RationalMethodResult(
      flowM3s: runoffCoefficient * intensityMmHr * areaHa / 360,
    );
  }

  /// Screening-level buried pipe buoyancy check.
  ///
  /// Soil resistance is represented as a submerged vertical prism with width
  /// equal to the pipe outside diameter. It intentionally excludes side shear,
  /// anchors, slabs and other project-specific restraint mechanisms.
  static PipeBuoyancyResult pipeBuoyancy({
    required double outsideDiameterM,
    required double insideDiameterM,
    required double lengthM,
    required double pipeDensityKgM3,
    required double soilCoverM,
    required double submergedSoilUnitWeightKnM3,
    double waterDensityKgM3 = 1000,
  }) {
    _positive(outsideDiameterM, 'outsideDiameter');
    _positive(insideDiameterM, 'insideDiameter');
    _positive(lengthM, 'length');
    _positive(pipeDensityKgM3, 'pipeDensity');
    if (insideDiameterM >= outsideDiameterM) {
      throw ArgumentError('insideDiameter must be less than outsideDiameter');
    }
    if (soilCoverM < 0) throw ArgumentError('soilCover must be non-negative');
    if (submergedSoilUnitWeightKnM3 < 0) {
      throw ArgumentError('submergedSoilUnitWeight must be non-negative');
    }

    final displacedVolume =
        math.pi * outsideDiameterM * outsideDiameterM / 4 * lengthM;
    final pipeMaterialVolume = math.pi *
        (outsideDiameterM * outsideDiameterM -
            insideDiameterM * insideDiameterM) /
        4 *
        lengthM;
    const g = 9.80665;
    final buoyantForceKn = waterDensityKgM3 * g * displacedVolume / 1000;
    final pipeWeightKn = pipeDensityKgM3 * g * pipeMaterialVolume / 1000;
    final soilWeightKn =
        submergedSoilUnitWeightKnM3 * outsideDiameterM * soilCoverM * lengthM;
    final resistingForce = pipeWeightKn + soilWeightKn;
    return PipeBuoyancyResult(
      buoyantForceKn: buoyantForceKn,
      pipeWeightKn: pipeWeightKn,
      soilWeightKn: soilWeightKn,
      resistingForceKn: resistingForce,
      factorOfSafety:
          buoyantForceKn == 0 ? double.infinity : resistingForce / buoyantForceKn,
    );
  }

  static DetentionResult constantFlowDetention({
    required double inflowM3s,
    required double allowableOutflowM3s,
    required double durationMinutes,
  }) {
    if (inflowM3s < 0) throw ArgumentError('inflow must be non-negative');
    if (allowableOutflowM3s < 0) {
      throw ArgumentError('allowableOutflow must be non-negative');
    }
    _positive(durationMinutes, 'duration');
    final excess =
        math.max(0.0, inflowM3s - allowableOutflowM3s).toDouble();
    return DetentionResult(
      inflowM3s: inflowM3s,
      outflowM3s: allowableOutflowM3s,
      storageM3: excess * durationMinutes * 60,
    );
  }

  static void _positive(double value, String name) {
    if (!value.isFinite || value <= 0) {
      throw ArgumentError('$name must be greater than zero');
    }
  }
}
