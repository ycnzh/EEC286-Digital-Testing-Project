% MATLAB Script for ISCAS'85 Fault Coverage Analysis
% Generates 3 separate figures (2x2 subplots each) with legends on EVERY subplot
clear; clc; close all;

% =========================================================
% CONFIGURATION
% =========================================================
% Define the 4 circuits for the 2x2 grid
circuits = {'c432', 'c880', 'c3540', 'c7552'}; 

% Define the relative path to where your Python scripts save the CSVs
data_dir = '../coverage_results/plot_data/';

% Define the 3 algorithms being compared
algorithms = {'Fully Random', 'D-Algorithm', 'PODEM'};

% Colors for consistent plotting
colors = lines(3);

% =========================================================
% INITIALIZE FIGURES
% =========================================================
fig1 = figure('Name', 'Coverage vs Vectors', 'Position', [50, 50, 1000, 700]);
fig2 = figure('Name', 'Coverage vs Time', 'Position', [100, 100, 1000, 700]);
fig3 = figure('Name', 'Improvement per Vector', 'Position', [150, 150, 1000, 700]);

% =========================================================
% LOAD DATA AND PLOT
% =========================================================
for c_idx = 1:length(circuits)
    circuit_name = circuits{c_idx};
    
    % Expected filenames for this specific circuit
    filenames = {
        sprintf('random_sim_%s.csv', circuit_name), ...
        sprintf('dalgo_sim_%s.csv', circuit_name), ...
        sprintf('podem_sim_%s.csv', circuit_name)
    };
    
    valid_legends = {};
    
    % --- PRE-SCAN: Find the minimum total number of vectors ---
    min_total_vectors = inf;
    for a_idx = 1:length(algorithms)
        filepath = fullfile(data_dir, filenames{a_idx});
        if isfile(filepath)
            tmp_data = readtable(filepath);
            min_total_vectors = min(min_total_vectors, max(tmp_data.Vector_Index));
        end
    end
    
    if isinf(min_total_vectors)
        min_total_vectors = 100; % Fallback if no data is found
    end
    % ----------------------------------------------------------
    
    for a_idx = 1:length(algorithms)
        filepath = fullfile(data_dir, filenames{a_idx});
        
        if isfile(filepath)
            fprintf('[*] Loading data for %s: %s\n', upper(circuit_name), algorithms{a_idx});
            data = readtable(filepath);
            
            vec_idx   = data.Vector_Index;
            time_sec  = data.Time_Seconds;
            coverage  = data.Coverage_Percent;
            delta_cov = data.Delta_Coverage;
            
            % Plot 1: Coverage vs Vectors (Truncated to min_total_vectors)
            figure(fig1); subplot(2, 2, c_idx); hold on; grid on;
            valid_idx = vec_idx <= min_total_vectors; % Filter array
            plot(vec_idx(valid_idx), coverage(valid_idx), 'LineWidth', 2.0, 'Color', colors(a_idx,:));
            
            % Plot 2: Coverage vs Time (Full Data)
            figure(fig2); subplot(2, 2, c_idx); hold on; grid on;
            plot(time_sec, coverage, 'LineWidth', 2.0, 'Color', colors(a_idx,:));
            
            % Plot 3: Delta Coverage (Scatter, Full Data)
            figure(fig3); subplot(2, 2, c_idx); hold on; grid on;
            active_indices = delta_cov > 0; % Filter out 0 to allow log scale
            scatter(vec_idx(active_indices), delta_cov(active_indices), 20, colors(a_idx,:), 'filled', 'MarkerEdgeColor', 'none');
            
            valid_legends{end+1} = algorithms{a_idx};
        else
            fprintf('[ ] File not found, skipping: %s\n', filepath);
        end
    end
    
    % =========================================================
    % FORMATTING SUBPLOTS
    % =========================================================
    
    % Format Fig 1: Coverage vs Vectors
    figure(fig1); subplot(2, 2, c_idx);
    title(sprintf('%s: Coverage vs. Vectors', upper(circuit_name)), 'FontSize', 12, 'FontWeight', 'bold');
    xlabel('Test Vector Index', 'FontSize', 10);
    ylabel('Fault Coverage (%)', 'FontSize', 10);
    xlim([0 min_total_vectors]); % Snap the X-axis tightly to the truncated data
    ylim([0 100]);
    if ~isempty(valid_legends)
        legend(valid_legends, 'Location', 'southeast', 'FontSize', 10);
    end
    
    % Format Fig 2: Coverage vs Time
    figure(fig2); subplot(2, 2, c_idx);
    title(sprintf('%s: Coverage vs. Execution Time', upper(circuit_name)), 'FontSize', 12, 'FontWeight', 'bold');
    xlabel('Execution Time (Seconds)', 'FontSize', 10);
    ylabel('Fault Coverage (%)', 'FontSize', 10);
    ylim([0 100]);
    if ~isempty(valid_legends)
        legend(valid_legends, 'Location', 'southeast', 'FontSize', 10);
    end
    
    % Format Fig 3: Improvement per Vector
    figure(fig3); subplot(2, 2, c_idx);
    title(sprintf('%s: Improvement per Vector', upper(circuit_name)), 'FontSize', 12, 'FontWeight', 'bold');
    xlabel('Test Vector Index', 'FontSize', 10);
    ylabel('\Delta Fault Coverage (%)', 'FontSize', 10);
    % set(gca, 'YScale', 'log'); % Apply Log Scale to Y-Axis
    if ~isempty(valid_legends)
        legend(valid_legends, 'Location', 'northeast', 'FontSize', 10);
    end
end

disp('========================================');
disp('All three figures generated successfully!');