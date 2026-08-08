import 'package:flutter/material.dart';

import '../core/engineering_calculators.dart';

class EngineeringScreen extends StatefulWidget {
  const EngineeringScreen({super.key});

  @override
  State<EngineeringScreen> createState() => _EngineeringScreenState();
}

class _EngineeringScreenState extends State<EngineeringScreen> {
  final _diameter = TextEditingController(text: '0.45');
  final _roughness = TextEditingController(text: '0.013');
  final _slope = TextEditingController(text: '0.005');

  final _coefficient = TextEditingController(text: '0.8');
  final _intensity = TextEditingController(text: '100');
  final _area = TextEditingController(text: '1.0');

  final _outsideDiameter = TextEditingController(text: '0.55');
  final _insideDiameter = TextEditingController(text: '0.45');
  final _pipeLength = TextEditingController(text: '1.0');
  final _pipeDensity = TextEditingController(text: '2400');
  final _soilCover = TextEditingController(text: '0.75');
  final _soilUnitWeight = TextEditingController(text: '10');

  final _detentionInflow = TextEditingController(text: '0.20');
  final _detentionOutflow = TextEditingController(text: '0.10');
  final _detentionDuration = TextEditingController(text: '30');

  @override
  void dispose() {
    for (final controller in [
      _diameter,
      _roughness,
      _slope,
      _coefficient,
      _intensity,
      _area,
      _outsideDiameter,
      _insideDiameter,
      _pipeLength,
      _pipeDensity,
      _soilCover,
      _soilUnitWeight,
      _detentionInflow,
      _detentionOutflow,
      _detentionDuration,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  double _number(TextEditingController controller) =>
      double.parse(controller.text.trim());

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 4,
      child: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 24, 24, 10),
              child: Row(
                children: [
                  const Icon(Icons.engineering_rounded, size: 34),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Engineering', style: Theme.of(context).textTheme.headlineSmall),
                        const SizedBox(height: 2),
                        Text(
                          'Deterministic civil engineering calculation tools',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const TabBar(
              isScrollable: true,
              tabs: [
                Tab(text: 'Pipe capacity'),
                Tab(text: 'Rational Method'),
                Tab(text: 'Buoyancy'),
                Tab(text: 'Detention'),
              ],
            ),
            Expanded(
              child: TabBarView(
                children: [
                  _calculatorPage(
                    title: 'Manning full-pipe capacity',
                    note: 'Assumes steady, uniform, full circular pipe flow.',
                    fields: [
                      _field('Internal diameter', 'm', _diameter),
                      _field('Manning n', '', _roughness),
                      _field('Hydraulic grade', 'm/m', _slope),
                    ],
                    calculate: () {
                      final result = EngineeringCalculators.fullCircularPipe(
                        diameterM: _number(_diameter),
                        roughnessN: _number(_roughness),
                        slope: _number(_slope),
                      );
                      return [
                        _result('Flow', '${result.flowM3s.toStringAsFixed(3)} m³/s'),
                        _result('Flow', '${(result.flowM3s * 1000).toStringAsFixed(0)} L/s'),
                        _result('Velocity', '${result.velocityMs.toStringAsFixed(2)} m/s'),
                      ];
                    },
                  ),
                  _calculatorPage(
                    title: 'Rational Method peak flow',
                    note: 'Q = C i A using i in mm/h and catchment area in hectares.',
                    fields: [
                      _field('Runoff coefficient C', '0–1', _coefficient),
                      _field('Rainfall intensity', 'mm/h', _intensity),
                      _field('Catchment area', 'ha', _area),
                    ],
                    calculate: () {
                      final result = EngineeringCalculators.rationalMethod(
                        runoffCoefficient: _number(_coefficient),
                        intensityMmHr: _number(_intensity),
                        areaHa: _number(_area),
                      );
                      return [
                        _result('Peak flow', '${result.flowM3s.toStringAsFixed(3)} m³/s'),
                        _result('Peak flow', '${result.flowLs.toStringAsFixed(0)} L/s'),
                      ];
                    },
                  ),
                  _calculatorPage(
                    title: 'Buried pipe buoyancy screening',
                    note:
                        'Screening only. Assumes full submergence and a vertical submerged-soil prism equal to the pipe outside diameter. Excludes side shear, anchors, slabs and project-specific load factors.',
                    fields: [
                      _field('Outside diameter', 'm', _outsideDiameter),
                      _field('Inside diameter', 'm', _insideDiameter),
                      _field('Pipe length checked', 'm', _pipeLength),
                      _field('Pipe material density', 'kg/m³', _pipeDensity),
                      _field('Soil cover above crown', 'm', _soilCover),
                      _field('Submerged soil unit weight', 'kN/m³', _soilUnitWeight),
                    ],
                    calculate: () {
                      final result = EngineeringCalculators.pipeBuoyancy(
                        outsideDiameterM: _number(_outsideDiameter),
                        insideDiameterM: _number(_insideDiameter),
                        lengthM: _number(_pipeLength),
                        pipeDensityKgM3: _number(_pipeDensity),
                        soilCoverM: _number(_soilCover),
                        submergedSoilUnitWeightKnM3: _number(_soilUnitWeight),
                      );
                      return [
                        _result('Buoyant force', '${result.buoyantForceKn.toStringAsFixed(1)} kN'),
                        _result('Resisting force', '${result.resistingForceKn.toStringAsFixed(1)} kN'),
                        _result('Factor of safety', result.factorOfSafety.toStringAsFixed(2)),
                        _result('Screening result', result.stable ? 'Resisting > uplift' : 'Uplift exceeds resistance'),
                      ];
                    },
                  ),
                  _calculatorPage(
                    title: 'Constant-flow detention sizing',
                    note:
                        'Screening helper only. Assumes constant inflow and allowable outflow for the selected duration; use a hydrograph/routing method for design.',
                    fields: [
                      _field('Peak inflow', 'm³/s', _detentionInflow),
                      _field('Allowable outflow', 'm³/s', _detentionOutflow),
                      _field('Critical duration', 'min', _detentionDuration),
                    ],
                    calculate: () {
                      final result = EngineeringCalculators.constantFlowDetention(
                        inflowM3s: _number(_detentionInflow),
                        allowableOutflowM3s: _number(_detentionOutflow),
                        durationMinutes: _number(_detentionDuration),
                      );
                      return [
                        _result('Required storage', '${result.storageM3.toStringAsFixed(1)} m³'),
                        _result('Excess flow', '${((result.inflowM3s - result.outflowM3s).clamp(0, double.infinity) * 1000).toStringAsFixed(0)} L/s'),
                      ];
                    },
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _calculatorPage({
    required String title,
    required String note,
    required List<Widget> fields,
    required List<Widget> Function() calculate,
  }) {
    return StatefulBuilder(
      builder: (context, setLocalState) {
        List<Widget>? results;
        String? error;
        return _LocalCalculatorBody(
          title: title,
          note: note,
          fields: fields,
          onCalculate: () {
            setLocalState(() {
              try {
                results = calculate();
                error = null;
              } catch (e) {
                results = null;
                error = 'Check the entered values and units.';
              }
            });
          },
          resultBuilder: () => results,
          errorBuilder: () => error,
        );
      },
    );
  }

  Widget _field(String label, String unit, TextEditingController controller) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: TextField(
          controller: controller,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: InputDecoration(
            labelText: label,
            suffixText: unit.isEmpty ? null : unit,
            border: const OutlineInputBorder(),
          ),
        ),
      );

  Widget _result(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          children: [
            Expanded(child: Text(label)),
            Text(value, style: const TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
      );
}

class _LocalCalculatorBody extends StatefulWidget {
  const _LocalCalculatorBody({
    required this.title,
    required this.note,
    required this.fields,
    required this.onCalculate,
    required this.resultBuilder,
    required this.errorBuilder,
  });

  final String title;
  final String note;
  final List<Widget> fields;
  final VoidCallback onCalculate;
  final List<Widget>? Function() resultBuilder;
  final String? Function() errorBuilder;

  @override
  State<_LocalCalculatorBody> createState() => _LocalCalculatorBodyState();
}

class _LocalCalculatorBodyState extends State<_LocalCalculatorBody> {
  @override
  Widget build(BuildContext context) {
    final results = widget.resultBuilder();
    final error = widget.errorBuilder();
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(widget.title, style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 6),
                  Text(widget.note, style: Theme.of(context).textTheme.bodySmall),
                  const SizedBox(height: 20),
                  ...widget.fields,
                  FilledButton.icon(
                    onPressed: widget.onCalculate,
                    icon: const Icon(Icons.calculate_rounded),
                    label: const Text('Calculate'),
                  ),
                  if (error != null) ...[
                    const SizedBox(height: 16),
                    Text(error, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  ],
                  if (results != null) ...[
                    const Divider(height: 32),
                    ...results,
                  ],
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}
