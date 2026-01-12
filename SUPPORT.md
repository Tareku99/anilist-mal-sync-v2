# Support

## Getting Help

If you need help with AniList-MAL Sync, here are the best ways to get support:

### Documentation

1. **README.md** - Start here for setup and usage instructions
2. **CONTRIBUTING.md** - Guidelines for contributing and updating diagrams

### Issues

- **Bug Reports**: [Open an issue](https://github.com/Tareku99/anilist-mal-sync/issues/new?template=bug_report.md) with detailed information
- **Feature Requests**: [Open an issue](https://github.com/Tareku99/anilist-mal-sync/issues/new?template=feature_request.md) describing your idea
- **Questions**: Use [GitHub Discussions](https://github.com/Tareku99/anilist-mal-sync/discussions) for general questions

### Before Asking for Help

Please check:

1. ✅ **README.md** - Your question might be answered in the documentation
2. ✅ **Existing Issues** - Search for similar issues that might already be resolved
3. ✅ **Closed Issues** - Your problem might have been solved before

### What to Include When Asking for Help

When opening an issue or asking a question, please include:

- **Version**: Docker image version or Python package version
- **Environment**: OS, Python version (if applicable), Docker version (if applicable)
- **Configuration**: Relevant parts of your `config.yaml` (remove sensitive credentials!)
- **Logs**: Error messages or relevant log output
- **Steps to Reproduce**: Clear steps to reproduce the issue
- **Expected Behavior**: What you expected to happen
- **Actual Behavior**: What actually happened

### Common Issues

#### OAuth Authentication Fails

- Verify your OAuth redirect URIs match exactly (no trailing slashes, correct protocol)
- Check that your client ID and secret are correct
- Ensure the OAuth callback port (default: 18080) is accessible

#### Sync Not Working

- Check that tokens are valid: `anilist-mal-sync auth`
- Verify your configuration is valid
- Check logs for error messages
- Try running with `--dry-run` to see what would be synced

#### Configuration Issues

- Ensure all required fields are filled in `data/config.yaml`
- Check for placeholder values that need to be replaced
- Verify YAML syntax is correct (no tabs, proper indentation)

### Community

- **Discussions**: [GitHub Discussions](https://github.com/Tareku99/anilist-mal-sync/discussions) for questions and ideas
- **Issues**: [GitHub Issues](https://github.com/Tareku99/anilist-mal-sync/issues) for bugs and feature requests

### Security Issues

For security vulnerabilities, please see [SECURITY.md](SECURITY.md) for reporting instructions.
