# FeliCa Dumper

A tool for reading and extracting data from FeliCa smart cards

## Summary

FeliCa Dumper is a comprehensive Python tool for reading and extracting data from FeliCa smart cards. It supports multiple system codes, automatic service discovery, authenticated data access, and provides a rich terminal interface with progress tracking and formatted output.

The tool can:
- Discover and process multiple system codes on a single card
- Automatically detect available areas and services
- Authenticate with cryptographic keys for protected services
- Extract block data with optimized batch processing
- Display results in a user-friendly format with detailed statistics

## Requirements

### Hardware
- FeliCa-compatible NFC card reader (USB connection)
- FeliCa Standard cards (various system codes supported)

### Software
- Python 3.13 or higher
- Poetry (for dependency management)
- USB NFC reader drivers

## Installation

```bash
git clone <repository-url>
cd felica-dumper
poetry install
```

## Usage

### Basic Usage

```bash
# Use default keys.csv file
poetry run dump-felica

# Specify custom keys file
poetry run dump-felica --keys /path/to/your/keys.csv
poetry run dump-felica -k custom_keys.csv

# Save results to text file
poetry run dump-felica -o results.txt

# Use custom keys and save to file
poetry run dump-felica -k mykeys.csv -o output.txt
```

### Command Line Options

- `--keys, -k`: Path to the keys CSV file (default: `keys.csv`)
- `--output, -o`: Path to output text file for saving extraction results (optional)

### Workflow

1. **Place the FeliCa card** on your NFC reader
2. **Run the command** - The tool will automatically:
   - Detect the card and display basic information
   - Discover all available system codes
   - For each system code:
     - Load appropriate authentication keys
     - Discover areas and services
     - Get key version information
     - Process services with authentication as needed
     - Extract and display block data
3. **Review results** - The tool provides detailed statistics and extracted data

## Key File Format

The authentication keys should be provided in CSV format with the following columns:

```csv
system_code,node,version,key
0003,FFFF,3,0123456789ABCDEF
0003,0000,3,0001020304050607
FE00,FFFF,0,08090A0B0C0D0E0F
FE00,0000,0,FEDCBA9876543210
```

### Key File Structure:
- **system_code**: Hexadecimal system code (e.g., `0003`, `FE00`)
- **node**: Node ID in hexadecimal (e.g., `FFFF` for system key, `0000` for root area key)
- **version**: Key version number
- **key**: 16-character hexadecimal authentication key

## Supported Cards

- FeliCa Standard cards with various system codes

## Output Features

The tool provides rich terminal output including:

- **Card Information**: Product type, system codes, IDm/PMm
- **Discovery Progress**: Real-time progress bars for area/service discovery
- **Key Information**: Available keys and versions for each system
- **Service Tree**: Hierarchical view of discovered services
- **Processing Status**: Batch processing with success/failure tracking
- **Data Results**: Extracted block data with timestamps
- **Summary Statistics**: Total blocks read, processing time, success rates

## Architecture

The project is organized into several key modules:

- **`cli.py`**: Main command-line interface and application entry point
- **`core/`**: Core functionality modules
  - `authentication.py`: Key-based authentication handling
  - `key_manager.py`: Key loading and management
  - `service_processor.py`: Service discovery and data processing
  - `tag_reader.py`: Low-level NFC tag communication
- **`models/`**: Data models and constants
- **`ui/`**: User interface and display formatting
- **`utils/`**: Helper functions and utilities

## Development

### Setup Development Environment

```bash
git clone https://github.com/soltia48/felica-dumper.git
cd felica-dumper
poetry install
poetry run black .  # Code formatting
```

### Dependencies

- **nfcpy**: NFC communication library (custom fork)
- **rich**: Terminal UI and formatting
- **black**: Code formatting (development)

## Authors

- KIRISHIKI Yudai

## License

[MIT](https://opensource.org/licenses/MIT)

Copyright (c) 2025 KIRISHIKI Yudai
