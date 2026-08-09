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

class PipeGradeResult {
  const PipeGradeResult({required this.slope, required this.gradePercent});
  final double slope;
  final double gradePercent;
}

class HeadlossResult {
  const HeadlossResult({
    required this.headlossM,
    required this.velocityMs,
    this.reynoldsNumber,
    this.frictionFactor,
  });

  final double headlossM;
  final double velocityMs;
  final double? reynoldsNumber;
  final double? frictionFactor;
}

class DischargeResult {
  const DischargeResult({required this.flowM3s, this.velocityMs});
  final double flowM3s;
  final double? velocityMs;
  double get flowLs => flowM3s * 1000;
}

class PumpPowerResult {
  const PumpPowerResult({
    required this.hydraulicPowerKw,
    required this.inputPowerKw,
  });
  final double hydraulicPowerKw;
  final double inputPowerKw;
}

class CriticalDepthResult {
  const CriticalDepthResult({required this.depthM, required this.velocityMs});
  final double depthM;
  final double velocityMs;
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
    return _manning(area, hydraulicRadius, roughnessN, slope);
  }

  static ManningResult partFullCircularPipe({
    required double diameterM,
    required double depthM,
    required double roughnessN,
    required double slope,
  }) {
    _positive(diameterM, 'diameter');
    _positive(depthM, 'depth');
    _positive(roughnessN, 'roughness');
    _positive(slope, 'slope');
    if (depthM > diameterM) throw ArgumentError('depth cannot exceed diameter');

    final radius = diameterM / 2;
    final theta = 2 * math.acos((radius - depthM) / radius);
    final area = radius * radius * (theta - math.sin(theta)) / 2;
    final wettedPerimeter = radius * theta;
    final hydraulicRadius = area / wettedPerimeter;
    return _manning(area, hydraulicRadius, roughnessN, slope);
  }

  static PipeGradeResult minimumCircularPipeGrade({
    required double diameterM,
    required double roughnessN,
    required double targetFlowM3s,
  }) {
    _positive(diameterM, 'diameter');
    _positive(roughnessN, 'roughness');
    _positive(targetFlowM3s, 'targetFlow');
    final area = math.pi * diameterM * diameterM / 4;
    final hydraulicRadius = diameterM / 4;
    final denominator = area * math.pow(hydraulicRadius, 2 / 3).toDouble();
    final slope = math.pow(targetFlowM3s * roughnessN / denominator, 2).toDouble();
    return PipeGradeResult(slope: slope, gradePercent: slope * 100);
  }

  static ManningResult rectangularChannel({
    required double widthM,
    required double depthM,
    required double roughnessN,
    required double slope,
  }) {
    _positive(widthM, 'width');
    _positive(depthM, 'depth');
    _positive(roughnessN, 'roughness');
    _positive(slope, 'slope');
    final area = widthM * depthM;
    final wettedPerimeter = widthM + 2 * depthM;
    return _manning(area, area / wettedPerimeter, roughnessN, slope);
  }

  static ManningResult trapezoidalChannel({
    required double bottomWidthM,
    required double depthM,
    required double sideSlopeHorizontalToVertical,
    required double roughnessN,
    required double slope,
  }) {
    _positive(bottomWidthM, 'bottomWidth');
    _positive(depthM, 'depth');
    if (sideSlopeHorizontalToVertical < 0) {
      throw ArgumentError('sideSlope must be non-negative');
    }
    _positive(roughnessN, 'roughness');
    _positive(slope, 'slope');
    final z = sideSlopeHorizontalToVertical;
    final area = depthM * (bottomWidthM + z * depthM);
    final wettedPerimeter = bottomWidthM + 2 * depthM * math.sqrt(1 + z * z);
    return _manning(area, area / wettedPerimeter, roughnessN, slope);
  }

  static CriticalDepthResult rectangularCriticalDepth({
    required double flowM3s,
    required double widthM,
  }) {
    _positive(flowM3s, 'flow');
    _positive(widthM, 'width');
    const g = 9.80665;
    final depth = math.pow(flowM3s * flowM3s / (g * widthM * widthM), 1 / 3).toDouble();
    return CriticalDepthResult(
      depthM: depth,
      velocityMs: flowM3s / (widthM * depth),
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

  static DischargeResult rectangularWeir({
    required double dischargeCoefficient,
    required double widthM,
    required double headM,
  }) {
    _positive(dischargeCoefficient, 'dischargeCoefficient');
    _positive(widthM, 'width');
    _positive(headM, 'head');
    const g = 9.80665;
    final flow = (2 / 3) * dischargeCoefficient * widthM * math.sqrt(2 * g) * math.pow(headM, 1.5);
    return DischargeResult(flowM3s: flow.toDouble());
  }

  static DischargeResult circularOrifice({
    required double dischargeCoefficient,
    required double diameterM,
    required double headM,
  }) {
    _positive(dischargeCoefficient, 'dischargeCoefficient');
    _positive(diameterM, 'diameter');
    _positive(headM, 'head');
    const g = 9.80665;
    final area = math.pi * diameterM * diameterM / 4;
    final velocity = dischargeCoefficient * math.sqrt(2 * g * headM);
    return DischargeResult(flowM3s: area * velocity, velocityMs: velocity);
  }

  static HeadlossResult hazenWilliams({
    required double flowM3s,
    required double diameterM,
    required double lengthM,
    required double coefficientC,
  }) {
    _positive(flowM3s, 'flow');
    _positive(diameterM, 'diameter');
    _positive(lengthM, 'length');
    _positive(coefficientC, 'coefficientC');
    final area = math.pi * diameterM * diameterM / 4;
    final headloss = 10.67 * lengthM * math.pow(flowM3s, 1.852) /
        (math.pow(coefficientC, 1.852) * math.pow(diameterM, 4.87));
    return HeadlossResult(
      headlossM: headloss.toDouble(),
      velocityMs: flowM3s / area,
    );
  }

  static HeadlossResult darcyWeisbach({
    required double flowM3s,
    required double diameterM,
    required double lengthM,
    required double absoluteRoughnessMm,
    double kinematicViscosityM2s = 1.004e-6,
  }) {
    _positive(flowM3s, 'flow');
    _positive(diameterM, 'diameter');
    _positive(lengthM, 'length');
    if (absoluteRoughnessMm < 0) throw ArgumentError('roughness must be non-negative');
    _positive(kinematicViscosityM2s, 'kinematicViscosity');
    const g = 9.80665;
    final area = math.pi * diameterM * diameterM / 4;
    final velocity = flowM3s / area;
    final reynolds = velocity * diameterM / kinematicViscosityM2s;
    final relativeRoughness = absoluteRoughnessMm / 1000 / diameterM;
    final frictionFactor = reynolds < 2300
        ? 64 / reynolds
        : 0.25 /
            math.pow(
              math.log((relativeRoughness / 3.7) + (5.74 / math.pow(reynolds, 0.9))) / math.ln10,
              2,
            );
    final headloss = frictionFactor * (lengthM / diameterM) * velocity * velocity / (2 * g);
    return HeadlossResult(
      headlossM: headloss.toDouble(),
      velocityMs: velocity,
      reynoldsNumber: reynolds,
      frictionFactor: frictionFactor.toDouble(),
    );
  }

  /// Minor (fitting/valve/bend) headloss using an entered sum of K coefficients:
  /// h_L = K * V^2 / (2g). K values remain a user input rather than a hidden
  /// default tied to a specific fitting catalogue or standard.
  static HeadlossResult minorLoss({
    required double flowM3s,
    required double diameterM,
    required double sumKValues,
  }) {
    _positive(flowM3s, 'flow');
    _positive(diameterM, 'diameter');
    if (sumKValues < 0) throw ArgumentError('sumKValues must be non-negative');
    const g = 9.80665;
    final area = math.pi * diameterM * diameterM / 4;
    final velocity = flowM3s / area;
    final headloss = sumKValues * velocity * velocity / (2 * g);
    return HeadlossResult(headlossM: headloss, velocityMs: velocity);
  }

  static PumpPowerResult pumpPower({
    required double flowM3s,
    required double totalHeadM,
    required double efficiencyPercent,
    double fluidDensityKgM3 = 1000,
  }) {
    _positive(flowM3s, 'flow');
    _positive(totalHeadM, 'totalHead');
    if (efficiencyPercent <= 0 || efficiencyPercent > 100) {
      throw ArgumentError('efficiencyPercent must be > 0 and <= 100');
    }
    _positive(fluidDensityKgM3, 'fluidDensity');
    const g = 9.80665;
    final hydraulicKw = fluidDensityKgM3 * g * flowM3s * totalHeadM / 1000;
    return PumpPowerResult(
      hydraulicPowerKw: hydraulicKw,
      inputPowerKw: hydraulicKw / (efficiencyPercent / 100),
    );
  }

  /// Screening-level buried pipe buoyancy check.
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

    final displacedVolume = math.pi * outsideDiameterM * outsideDiameterM / 4 * lengthM;
    final pipeMaterialVolume = math.pi *
        (outsideDiameterM * outsideDiameterM - insideDiameterM * insideDiameterM) /
        4 *
        lengthM;
    const g = 9.80665;
    final buoyantForceKn = waterDensityKgM3 * g * displacedVolume / 1000;
    final pipeWeightKn = pipeDensityKgM3 * g * pipeMaterialVolume / 1000;
    final soilWeightKn = submergedSoilUnitWeightKnM3 * outsideDiameterM * soilCoverM * lengthM;
    final resistingForce = pipeWeightKn + soilWeightKn;
    return PipeBuoyancyResult(
      buoyantForceKn: buoyantForceKn,
      pipeWeightKn: pipeWeightKn,
      soilWeightKn: soilWeightKn,
      resistingForceKn: resistingForce,
      factorOfSafety: buoyantForceKn == 0 ? double.infinity : resistingForce / buoyantForceKn,
    );
  }

  static DetentionResult constantFlowDetention({
    required double inflowM3s,
    required double allowableOutflowM3s,
    required double durationMinutes,
  }) {
    if (inflowM3s < 0) throw ArgumentError('inflow must be non-negative');
    if (allowableOutflowM3s < 0) throw ArgumentError('allowableOutflow must be non-negative');
    _positive(durationMinutes, 'duration');
    final excess = math.max(0.0, inflowM3s - allowableOutflowM3s).toDouble();
    return DetentionResult(
      inflowM3s: inflowM3s,
      outflowM3s: allowableOutflowM3s,
      storageM3: excess * durationMinutes * 60,
    );
  }

  static ManningResult _manning(
    double areaM2,
    double hydraulicRadiusM,
    double roughnessN,
    double slope,
  ) {
    final flow = (1 / roughnessN) *
        areaM2 *
        math.pow(hydraulicRadiusM, 2 / 3).toDouble() *
        math.sqrt(slope);
    return ManningResult(
      flowM3s: flow,
      velocityMs: flow / areaM2,
      areaM2: areaM2,
      hydraulicRadiusM: hydraulicRadiusM,
    );
  }

  static void _positive(double value, String name) {
    if (!value.isFinite || value <= 0) {
      throw ArgumentError('$name must be greater than zero');
    }
  }
}
