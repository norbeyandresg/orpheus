# Orpheus

Orpheus is a Python-based tool that allows you to synchronize your YouTube Music library by downloading selected playlists to your local machine. With Orpheus, you can view all your YouTube Music playlists, choose which ones to sync, and the application will handle the downloading process for you.

## Features

- **Playlist Selection**: Browse and select which of your YouTube Music playlists you want to download.
- **Local Synchronization**: Downloads new media and remove tracks that you already remove from YouTube Music
- **User-Friendly Interface**: Simple command-line interface for ease of use.

## Prerequisites

Before installing Orpheus, ensure you have the following installed on your system:

- **Python 3.x**: Orpheus requires Python 3.x to run. You can download it from the [official Python website](https://www.python.org/downloads/).

## Installation

To install Orpheus, follow these steps:

1. **Clone the Repository**: Begin by cloning the Orpheus repository from GitHub:

   ```bash
   git clone https://github.com/norbeyandresg/orpheus.git
   ```

2. **Navigate to the Project Directory**: Move into the Orpheus directory:

   ```bash
   cd orpheus
   ```

3. **Install Dependencies**: Install the required Python packages using `pip`:

   ```bash
   pip install -r requirements.txt
   ```

   This command will install all the necessary libraries listed in the `requirements.txt` file.

## Usage

To run Orpheus and start synchronizing your playlists:

1. **Execute the Application**: Launch the application by running:

   ```bash
   python ui.py
   ```

2. **Authenticate with YouTube Music**: Upon running the application for the first time, you'll be prompted to authenticate with your YouTube Music account. Follow the on-screen instructions to complete the authentication process.

3. **Select Playlists to Sync**: After authentication, Orpheus will display a list of your YouTube Music playlists. Use the interface to select the playlists you wish to download.

4. **Download Process**: Once you've made your selections, Orpheus will begin downloading the chosen playlists to your local machine. The downloaded files will be organized accordingly.

## Contributing

Contributions to Orpheus are welcome! If you have suggestions for improvements or encounter any issues, please consider contributing:

1. **Fork the Repository**: Click on the 'Fork' button at the top right of the [Orpheus GitHub page](https://github.com/norbeyandresg/orpheus).

2. **Create a New Branch**: In your forked repository, create a new branch for your feature or fix:

   ```bash
   git checkout -b feature-or-fix-name
   ```

3. **Make Your Changes**: Implement your feature or fix in your branch.

4. **Commit Your Changes**: Commit your changes with a descriptive message:

   ```bash
   git commit -m "Description of the feature or fix"
   ```

5. **Push to GitHub**: Push your changes to your forked repository:

   ```bash
   git push origin feature-or-fix-name
   ```

6. **Submit a Pull Request**: Go to the original Orpheus repository and submit a pull request detailing your changes.

## License

Orpheus is licensed under the [MIT License](LICENSE). Feel free to use, modify, and distribute this software in accordance with the license terms.


