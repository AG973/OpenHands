"""Mobile App Building tool for the CodeAct Agent.

Provides the agent with capabilities to create, build, and deploy
mobile applications using React Native and Expo.
"""

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk

_MOBILE_BUILD_DESCRIPTION = """Build, test, and deploy mobile applications for iOS and Android using React Native and Expo.

### Available Operations:

**Project Setup:**
1. **create_project** - Create a new React Native or Expo project from a template.
2. **install_dependencies** - Install project dependencies (npm/yarn).
3. **add_package** - Add a package to the mobile project.

**Development:**
4. **start_dev_server** - Start the Expo/React Native development server.
5. **generate_component** - Generate a new React Native component from a description.
6. **generate_screen** - Generate a new screen/page with navigation setup.
7. **add_navigation** - Set up or modify navigation (stack, tab, drawer).

**Building:**
8. **build_android** - Build the Android APK or AAB.
9. **build_ios** - Build the iOS app (requires macOS or EAS Build).
10. **build_web** - Build the web version of the app (Expo web).
11. **eas_build** - Trigger a cloud build using Expo Application Services (EAS).

**Testing:**
12. **run_tests** - Run the test suite for the mobile project.
13. **start_emulator** - Start an Android emulator or iOS simulator.
14. **preview_qr** - Generate a QR code for Expo Go preview on a real device.

**Deployment:**
15. **eas_submit_android** - Submit the Android build to Google Play Store via EAS.
16. **eas_submit_ios** - Submit the iOS build to Apple App Store via EAS.
17. **publish_update** - Publish an over-the-air update via EAS Update.

### Templates:
- **blank** - Minimal blank project
- **tabs** - Tab-based navigation layout
- **drawer** - Drawer navigation layout
- **stack** - Stack navigation layout
- **ecommerce** - E-commerce app template
- **social** - Social media app template
- **chat** - Chat/messaging app template

### Usage Notes:
- Expo is used by default for cross-platform compatibility (iOS + Android + Web).
- EAS Build handles cloud builds without needing local Android SDK or Xcode.
- Set EXPO_TOKEN for authenticated EAS operations.
- For App Store/Play Store submission, configure eas.json in the project.
"""

MobileBuildTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='mobile_build',
        description=_MOBILE_BUILD_DESCRIPTION,
        parameters={
            'type': 'object',
            'properties': {
                'operation': {
                    'type': 'string',
                    'description': 'The mobile build operation to perform.',
                    'enum': [
                        'create_project',
                        'install_dependencies',
                        'add_package',
                        'start_dev_server',
                        'generate_component',
                        'generate_screen',
                        'add_navigation',
                        'build_android',
                        'build_ios',
                        'build_web',
                        'eas_build',
                        'run_tests',
                        'start_emulator',
                        'preview_qr',
                        'eas_submit_android',
                        'eas_submit_ios',
                        'publish_update',
                    ],
                },
                'project_name': {
                    'type': 'string',
                    'description': 'Name of the mobile project to create.',
                },
                'project_path': {
                    'type': 'string',
                    'description': 'Path to the mobile project directory.',
                },
                'template': {
                    'type': 'string',
                    'description': 'Project template to use (blank, tabs, drawer, stack, ecommerce, social, chat).',
                    'enum': ['blank', 'tabs', 'drawer', 'stack', 'ecommerce', 'social', 'chat'],
                },
                'platform': {
                    'type': 'string',
                    'description': 'Target platform for build operations.',
                    'enum': ['android', 'ios', 'web', 'all'],
                },
                'component_name': {
                    'type': 'string',
                    'description': 'Name of the component or screen to generate.',
                },
                'component_description': {
                    'type': 'string',
                    'description': 'Description of the component or screen functionality for code generation.',
                },
                'package_name': {
                    'type': 'string',
                    'description': 'NPM package name to add (add_package operation).',
                },
                'navigation_type': {
                    'type': 'string',
                    'description': 'Type of navigation to set up.',
                    'enum': ['stack', 'tab', 'drawer', 'bottom-tab'],
                },
                'build_profile': {
                    'type': 'string',
                    'description': 'EAS build profile (development, preview, production).',
                    'enum': ['development', 'preview', 'production'],
                },
                'build_type': {
                    'type': 'string',
                    'description': 'Build output type for Android.',
                    'enum': ['apk', 'aab'],
                },
            },
            'required': ['operation'],
        },
    ),
)
