import 'package:flutter/material.dart';

import 'current_project_screen.dart';
import 'projects_screen.dart';

class ProjectsHubScreen extends StatelessWidget {
  const ProjectsHubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const DefaultTabController(
      length: 2,
      child: Column(
        children: [
          Material(
            child: SafeArea(
              bottom: false,
              child: TabBar(
                tabs: [
                  Tab(icon: Icon(Icons.folder_rounded), text: 'Projects'),
                  Tab(icon: Icon(Icons.adjust_rounded), text: 'Current'),
                ],
              ),
            ),
          ),
          Expanded(
            child: TabBarView(
              children: [
                ProjectsScreen(),
                CurrentProjectScreen(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
